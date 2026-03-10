# Upbit Trading Bot

## 📌 Main Code

**M_v3_2** - 매주 월요일 코인별로 +- 읽어서 csv 출력

**M_v3_3** - 시간 동기화, KRW 마켓에 없는건 자산검색할때 X 오류남이거때매

---

## 📈 Trading Bot 버전 기록

**TD_v5_1** - BTC:1% / ETH:1.5% / 기타:2% RSI 코인별 설정

**TD_v5_2** - 코인 추가 및 백테스터 추가 검증
- BTC, ADA, AVAX, DOT, TRX: 1%
- ETH: 1.5%
- SOL, XRP: 2%

**TD_v5_3** - DOT, AVAX, ADA: RSI limit 40 / BTC, ETH, TRX, SOL, XRP: RSI limit 50

**TD_v5_4** - 종목별 로그 코드 추가, 매주 월요일 코인별 손/실 체크

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
pkill -f @.py
nohup python3 @.py > @.log 2>&1 &
```
