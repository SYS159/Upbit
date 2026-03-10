import pyupbit
import time
import os
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

# --- [설정 및 환경변수] ---
ACCESS = os.getenv("UPBIT_ACCESS_KEY")
SECRET = os.getenv("UPBIT_SECRET_KEY")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

upbit = pyupbit.Upbit(ACCESS, SECRET)
KST = timezone(timedelta(hours=9))

WEEKLY_BASE_FILE = "weekly_base_asset.txt"
TRADE_LOG_FILE = "trade_log.csv"
DAILY_LOG_FILE = "weekly_assets_log.txt"

# --- [유틸리티 함수] ---

def send_discord_msg(message):
    try:
        requests.post(WEBHOOK_URL, json={"content": message}, timeout=5)
    except Exception as e:
        print(f"디스코드 전송 에러: {e}")

def save_file(filename, data, mode="w"):
    with open(filename, mode, encoding="utf-8") as f:
        f.write(data)

def load_weekly_base():
    if os.path.exists(WEEKLY_BASE_FILE):
        with open(WEEKLY_BASE_FILE, "r", encoding="utf-8") as f:
            return float(f.read())
    return None

def get_total_asset_info():
    """현재 총 자산 및 개별 종목 수익률 계산 (API 호출 최적화)"""
    balances = upbit.get_balances()
    if not balances:
        return None, ""

    total_eval = 0
    ticker_list = []
    balance_dict = {}

    # 1차 분류: 원화 및 코인 리스트업
    for b in balances:
        ticker = b['currency']
        amount = float(b['balance'])
        avg_buy = float(b['avg_buy_price'])
        
        if ticker == 'KRW':
            total_eval += amount
        else:
            full_ticker = f"KRW-{ticker}"
            ticker_list.append(full_ticker)
            balance_dict[full_ticker] = {"amount": amount, "avg_buy": avg_buy}

    # 현재가 일괄 조회 (API 효율성)
    current_prices = pyupbit.get_current_price(ticker_list)
    
    # current_prices가 단일 종목일 때 float, 여러 종목일 때 dict 반환 대응
    if len(ticker_list) == 1 and isinstance(current_prices, (int, float)):
        current_prices = {ticker_list[0]: current_prices}

    details = ""
    if current_prices:
        for t, price in current_prices.items():
            if price is None: continue
            info = balance_dict[t]
            eval_val = info['amount'] * price
            total_eval += eval_val
            
            p_rate = ((price - info['avg_buy']) / info['avg_buy'] * 100) if info['avg_buy'] > 0 else 0
            emoji = "📈" if p_rate >= 0 else "📉"
            details += f"> {emoji} **{t.split('-')[1]}**: {p_rate:+.2f}% (`{int(eval_val):,}`원)\n"
            
    return total_eval, details

def get_weekly_trade_summary():
    """매도 로그 분석 및 초기화"""
    if not os.path.exists(TRADE_LOG_FILE) or os.stat(TRADE_LOG_FILE).st_size == 0:
        return "이번 주 확정 수익 내역이 없습니다."
    
    summary = {}
    total_realized = 0
    with open(TRADE_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) < 3: continue
            ticker, profit = parts[1], int(parts[2])
            summary[ticker] = summary.get(ticker, 0) + profit
            total_realized += profit
            
    report = "🪙 **[주간 종목별 확정 수익 내역]**\n"
    for ticker, amount in sorted(summary.items(), key=lambda x: x[1], reverse=True):
        report += f"{'✅' if amount >= 0 else '❌'} **{ticker}**: `{amount:+,}원` 확정\n"
    report += f"\n💰 **주간 매도 수익 합계**: `{total_realized:+,}원`"
    
    save_file(TRADE_LOG_FILE, "") # 파일 비우기
    return report

# --- [메인 루프] ---

print("--- 업비트 주간 성적 추적 봇 V4.1 가동 ---")
send_discord_msg("🚀 **성적 추적 봇 V4.1** 가동 (최적화 완료)")

last_sent_hm = ""
daily_check_flag = False
weekly_base_asset = load_weekly_base()

while True:
    try:
        now = datetime.now(KST)
        current_hm = now.strftime("%H:%M")
        
        # 1. 자산 정보 가져오기
        total_eval, individual_details = get_total_asset_info()
        
        if total_eval is None:
            time.sleep(10)
            continue

        # 기준가 설정 (최초 실행 시)
        if weekly_base_asset is None:
            weekly_base_asset = total_eval
            save_file(WEEKLY_BASE_FILE, str(weekly_base_asset))

        weekly_profit_rate = ((total_eval - weekly_base_asset) / weekly_base_asset) * 100
        weekly_diff = total_eval - weekly_base_asset

        # 2. 정기 알림 (매시 정각 및 30분)
        if now.minute in [0, 30] and current_hm != last_sent_hm:
            status = f"📊 **[실시간 자산 리포트 - {current_hm}]**\n" \
                     f"{individual_details}\n" \
                     f"💰 **현재 총 자산**: `{int(total_eval):,}원` \n" \
                     f"📅 **주간 성적**: `{int(weekly_diff):+,}원` (**{weekly_profit_rate:+.2f}%**)\n" \
                     f"*(기준: 이번주 월요일 09:00)*"
            send_discord_msg(status)
            last_sent_hm = current_hm

        # 3. 매일 아침 9시 데일리 기록 및 월요일 최종 결산
        if now.hour == 9 and now.minute == 0 and not daily_check_flag:
            # 월요일 아침이면 주간 결산
            if now.weekday() == 0:
                trade_summary = get_weekly_trade_summary()
                daily_log = ""
                if os.path.exists(DAILY_LOG_FILE):
                    with open(DAILY_LOG_FILE, "r", encoding="utf-8") as f:
                        daily_log = f.read()
                
                final_msg = f"📅 **[지난주 투자 성적 최종 결산]**\n\n{trade_summary}\n\n" \
                            f"📝 **일별 자산 흐름:**\n```csv\n{daily_log}```\n" \
                            f"📈 **전체 자산 변동**: `{int(weekly_diff):+,}원` ({weekly_profit_rate:+.2f}%)\n" \
                            f"💰 **최종 총 자산**: `{int(total_eval):,}원`"
                send_discord_msg(final_msg)
                
                # 새로운 주 시작: 기준가 갱신 및 데일리 로그 초기화
                weekly_base_asset = total_eval
                save_file(WEEKLY_BASE_FILE, str(weekly_base_asset))
                save_file(DAILY_LOG_FILE, "") 
                send_discord_msg(f"🚩 **이번 주 기준가가 갱신되었습니다.**\n시작 자산: `{int(weekly_base_asset):,}원` 시작")
            
            # 매일 아침 자산 로그 저장
            log_line = f"{now.strftime('%Y-%m-%d')}, 자산: {int(total_eval):,}원, 수익률: {weekly_profit_rate:+.2f}%\n"
            save_file(DAILY_LOG_FILE, log_line, mode="a")
            daily_check_flag = True
            
        if now.hour != 9:
            daily_check_flag = False

        time.sleep(30) # 체크 주기 30초로 조정
        
    except Exception as e:
        print(f"메인 루프 에러: {e}")
        time.sleep(20)