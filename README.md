# Upbit Trading Bot

## ⚙️ 설치
```bash
git clone https://github.com/SYS159/Upbit.git
cd Upbit
```

## 🚀 실행
```bash
nohup python3 -u TD_v5_4.py > TD_v5_4.log 2>&1 &
nohup python3 -u M_v3_4.py > M_v3_4.log 2>&1 &
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
-  업비트 연결되어있는지 매 시간마다 테더 값 받아오기 구현했으나 주석처리

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

**라즈베리파이 명령어들**
```bash
ps -ef | grep python

pkill -f TD_v5_4.py
nohup python3 -u TD_v5_4.py > TD_v5_4.log 2>&1 &

pkill -f M_v3_4.py
nohup python3 -u  M_v3_4.py > M_v3_4.log 2>&1 &

-u가 있어야 로그 실시간으로 작성함.
```
