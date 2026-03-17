# Upbit Trading Bot

## ⚙️ 설치
```bash
git clone https://github.com/SYS159/Upbit.git
cd Upbit
```

## 🚀 실행
```bash
ps -ef | grep python
nohup python3 -u M_v3_4.py > M_v3_4.log 2>&1 &
nohup python3 -u UTD_v6_3.py > UTD_v6_3.log 2>&1 &
```

## 정지
```bash
pkill -f M_v3_4.py
pkill -f UTD_v6_3.py
```

## 📌 Main Code

**M_v3_3** 
- 시간 동기화
- KRW 마켓에 없는건 자산검색할때 X 오류남이거때매

**M_v3_4** 
- v3에서 코드 다듬기
- 주간수익률 분석

---

## 📈 Trading Code

**TD_v5_1** 
- BTC:1% / ETH:1.5% / 기타:2% RSI 코인별 설정

**TD_v5_2** 
- 코인 추가 및 백테스터 추가 검증
- BTC, ADA, AVAX, DOT, TRX: 1%
- ETH: 1.5%
- SOL, XRP: 2%

**TD_v5_3** 
- DOT, AVAX, ADA: RSI limit 40 / BTC, ETH, TRX, SOL, XRP: RSI limit 50

**TD_v5_4** 
- 종목별 로그 코드 추가
- 매주 월요일 코인별 손/실 체크
- 업비트 연결되어있는지 매 시간마다 테더 값 받아오기 구현했으나 주석처리

**UTD_v5_5**
- 트레일링스탑에서 판매로직에 문제가 있어 수정 1.2% -> 0.7% 면 판매되어야 하지만 판매되지 않았음

**UTD_v6_1**
- 매수로직 수정 골든크로스 완화
- 낙주 있/없 코인별 수정
- RSI가 반등할때 구매

**UTD_v6_2**
- 파라미터 수정
- 음봉에는 골든크로스라도 매수 X

**UTH_v6_3**
- 코인 (종목)	이평선 (MA)	거래량 기준봉	낙주 줍기 (RSI Drop)	RSI 컷 (상/하한)	TS 발동
- KRW-NEAR	5 / 20선 (무거움)	10봉 (50분)	O 사용	30 / 50	1.50%
- KRW-BTC	3 / 15선 (빠름)	5봉 (25분)	O 사용	30 / 50	1.00%
- KRW-ETH	3 / 15선 (빠름)	5봉 (25분)	X 끄기	- / 60	1.50%
- KRW-LINK	3 / 15선 (빠름)	5봉 (25분)	X 끄기	- / 50	1.00%
- KRW-SOL	3 / 15선 (빠름)	20봉 (100분)	O 사용	25 / 50	1.50%
- KRW-XRP	3 / 15선 (빠름)	10봉 (50분)	O 사용	25 / 50	1.50%

## 📈 Back Testing Code

**UBT_v6_1** 
- RSI 낙주 있/없, 골든크로스 거래량 배율 수정 가능
- 코인 추가

**UBT_v6_2** 
- MA5, MA20으로 수정 테스트

---

## 💻 자주 쓰는 명령어

**파일 올리기 (push)**
```bash
git add 파일명.py
git commit -m "메시지"
git push
```

**파일 내리기 (pull)**
```bash
git pull
```
