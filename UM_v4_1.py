import pyupbit
import time
import os
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# --- [설정 및 환경변수] ---
ACCESS = os.getenv("UPBIT_ACCESS_KEY")
SECRET = os.getenv("UPBIT_SECRET_KEY")
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

upbit = pyupbit.Upbit(ACCESS, SECRET)
KST = timezone(timedelta(hours=9))

# 파일명 설정
WEEKLY_BASE_FILE = "weekly_base_asset.txt"
DAILY_BASE_FILE = "daily_base_asset.txt"  # [추가] 일일 기준가 파일
TRADE_LOG_FILE = "trade_log.csv"
DAILY_LOG_FILE = "weekly_assets_log.txt"

# --- [유틸리티 함수] ---

def send_discord_msg(message):
    """디스코드 웹훅 전송 및 로그 출력"""
    try:
        resp = requests.post(WEBHOOK_URL, json={"content": message}, timeout=5)
        now_str = datetime.now(KST).strftime('%H:%M:%S')
        print(f"[{now_str}] 디스코드 전송 상태: {resp.status_code}")
    except Exception as e:
        print(f"디스코드 전송 에러: {e}")

def save_file(filename, data, mode="w"):
    """파일 저장 로직"""
    try:
        with open(filename, mode, encoding="utf-8") as f:
            f.write(data)
    except Exception as e:
        print(f"파일 저장 에러 ({filename}): {e}")

def load_base_asset(filename):
    """기준 자산 불러오기 (주간/일간 공용)"""
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return float(f.read().strip())
        except:
            return None
    return None

def get_total_asset_info():
    """자산 정보 가져오기 (에러 종목 건너뛰기 기능 추가)"""
    try:
        balances = upbit.get_balances()
        if not balances: return None, ""

        total_eval = 0
        ticker_list = []
        balance_dict = {}

        for b in balances:
            ticker = b['currency']
            amount = float(b['balance'])
            avg_buy = float(b['avg_buy_price'])
            
            # 5000원 미만 자산 제외
            if ticker != 'KRW' and (amount * avg_buy) < 5000:
                continue

            if ticker == 'KRW':
                total_eval += amount
            else:
                full_ticker = f"KRW-{ticker}"
                ticker_list.append(full_ticker)
                balance_dict[full_ticker] = {"amount": amount, "avg_buy": avg_buy}

        details = ""
        if ticker_list:
            # 시세 조회 (Code not found 에러 방지를 위해 개별 예외 처리 보강)
            for t in ticker_list:
                try:
                    price = pyupbit.get_current_price(t)
                    if price is None or price <= 0:
                        continue # 마켓에 없는 코인은 무시
                    
                    info = balance_dict[t]
                    eval_val = info['amount'] * price
                    total_eval += eval_val
                    p_rate = ((price - info['avg_buy']) / info['avg_buy'] * 100) if info['avg_buy'] > 0 else 0
                    emoji = "📈" if p_rate >= 0 else "📉"
                    details += f"> {emoji} **{t.split('-')[1]}**: {p_rate:+.2f}% (`{int(eval_val):,}`원)\n"
                except Exception as e:
                    print(f"종목 조회 건너뜀 ({t}): {e}")
                    continue
        
        return total_eval, details
    except Exception as e:
        print(f"전체 자산 조회 중 치명적 에러: {e}")
        return None, ""

def get_weekly_trade_summary():
    """trade_log.csv 분석: 종목별 확정 수익 합산"""
    if not os.path.exists(TRADE_LOG_FILE):
        with open(TRADE_LOG_FILE, "w", encoding="utf-8") as f:
            pass
        return "이번 주 매도 확정 수익 내역이 없습니다."
    
    summary = {}
    total_realized = 0
    
    try:
        with open(TRADE_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) < 3: continue 
                
                try:
                    ticker = parts[1]        # 종목
                    profit = int(parts[2])   # 수익금
                    summary[ticker] = summary.get(ticker, 0) + profit
                    total_realized += profit
                except (ValueError, IndexError):
                    continue
        
        if not summary: 
            return "이번 주 확정 수익 내역이 없습니다."

        report = "🪙 **[주간 종목별 확정 수익 내역]**\n"
        sorted_summary = sorted(summary.items(), key=lambda x: x[1], reverse=True)
        
        for ticker, amount in sorted_summary:
            emoji = "✅" if amount >= 0 else "❌"
            report += f"{emoji} **{ticker}**: `{amount:+,}원` 확정\n"
            
        with open(TRADE_LOG_FILE, "w", encoding="utf-8") as f:
            pass
            
        return report
    except Exception as e:
        return f"수익 분석 중 에러 발생: {e}"

# --- [메인 실행부] ---

print("--- 업비트 주간/일간 성적 추적 봇 UM_v4_1 가동 ---")
send_discord_msg("🚀 **성적 추적 봇 UM_v4_1** 가동 시작 (일일 수익 추적 포함)")

last_sent_hm = ""
daily_check_flag = False

# 주간 및 일간 기준가 로드
weekly_base_asset = load_base_asset(WEEKLY_BASE_FILE)
daily_base_asset = load_base_asset(DAILY_BASE_FILE)

while True:
    try:
        now = datetime.now(KST)
        current_hm = now.strftime("%H:%M")
        
        # 1. 자산 데이터 갱신
        total_eval, individual_details = get_total_asset_info()
        
        if total_eval is not None:
            # 최초 실행 시 기준가 저장
            if weekly_base_asset is None:
                weekly_base_asset = total_eval
                save_file(WEEKLY_BASE_FILE, str(weekly_base_asset))
            
            # [추가] 최초 실행 시 일일 기준가 저장
            if daily_base_asset is None:
                daily_base_asset = total_eval
                save_file(DAILY_BASE_FILE, str(daily_base_asset))

            # 주간 성적 계산
            weekly_diff = total_eval - weekly_base_asset
            weekly_profit_rate = (weekly_diff / weekly_base_asset * 100) if weekly_base_asset > 0 else 0

            # [추가] 일일 성적 계산
            daily_diff = total_eval - daily_base_asset
            daily_profit_rate = (daily_diff / daily_base_asset * 100) if daily_base_asset > 0 else 0

            # 2. 정기 알림 (매시 정각)
            if now.minute in [0] and current_hm != last_sent_hm:
                status = f"📊 **[실시간 자산 리포트 - {current_hm}]**\n" \
                         f"{individual_details}\n" \
                         f"💰 **현재 총 자산**: `{int(total_eval):,}원` \n" \
                         f"☀️ **오늘 수익 (9시~)**: `{int(daily_diff):+,}원` (**{daily_profit_rate:+.2f}%**)\n" \
                         f"📅 **주간 수익 (월~)**: `{int(weekly_diff):+,}원` (**{weekly_profit_rate:+.2f}%**)"
                send_discord_msg(status)
                last_sent_hm = current_hm

            # 3. 매일 아침 9시 데일리 기록 및 월요일 최종 결산
            if now.hour == 9 and now.minute == 0 and not daily_check_flag:
                # [월요일 아침 9시] 주간 최종 리포트 전송
                if now.weekday() == 0:
                    trade_summary = get_weekly_trade_summary()
                    daily_log = "기록 없음"
                    if os.path.exists(DAILY_LOG_FILE):
                        with open(DAILY_LOG_FILE, "r", encoding="utf-8") as f:
                            daily_log = f.read()
                    
                    final_msg = f"📅 **[지난주 투자 성적 최종 결산]**\n\n" \
                                f"{trade_summary}\n\n" \
                                f"📝 **일별 자산 흐름:**\n```csv\n{daily_log}```\n" \
                                f"📈 **전체 자산 변동**: `{int(weekly_diff):+,}원` ({weekly_profit_rate:+.2f}%)\n" \
                                f"💰 **최종 총 자산**: `{int(total_eval):,}원`"
                    send_discord_msg(final_msg)
                    
                    # 새로운 주를 위한 초기화
                    weekly_base_asset = total_eval
                    save_file(WEEKLY_BASE_FILE, str(weekly_base_asset))
                    save_file(DAILY_LOG_FILE, "") # 데일리 로그 초기화
                    send_discord_msg(f"🚩 **이번 주 기준가가 갱신되었습니다.**\n시작 자산: `{int(weekly_base_asset):,}원`")

                # [추가] 매일 아침 9시: 일일 기준가 갱신 및 디스코드 알림
                daily_base_asset = total_eval
                save_file(DAILY_BASE_FILE, str(daily_base_asset))
                send_discord_msg(f"🚩 **{now.strftime('%m/%d')} 일일 기준가 갱신**\n오늘 시작 자산: `{int(daily_base_asset):,}원`")

                # [매일 아침 9시] 자산 로그 기록 (txt 파일에 추가)
                log_line = f"{now.strftime('%Y-%m-%d')}, 자산: {int(total_eval):,}원, 수익률: {weekly_profit_rate:+.2f}%\n"
                save_file(DAILY_LOG_FILE, log_line, mode="a")
                daily_check_flag = True
                print(f"[{now.strftime('%H:%M:%S')}] 일일 자산 기록 완료")

            # 9시가 지나면 플래그 리셋
            if now.hour != 9:
                daily_check_flag = False

        time.sleep(20) # 20초마다 체크

    except Exception as e:
        print(f"메인 루프 에러: {e}")
        time.sleep(10)