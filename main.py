import httpx
from mTransKey.transkey import mTransKey
from colorama import init, Fore, Style
from datetime import datetime
from flask import Flask, request
from json import dump, load
from logging import getLogger
from playwright.sync_api import sync_playwright
from random import randrange
from re import compile
from time import time, sleep
from urllib import parse

accounts = {}
with open("./accounts.json", "r") as f:
    accounts = load(f)

accessTokens = {}
with open("./accessTokens.json", "r", encoding="utf-8") as f:
    accessTokens = load(f)

altChars = {"~": "물결표시", "@": "골뱅이", "$": "달러기호", "^": "꺽쇠", "*": "별표", "(": "왼쪽괄호", ")": "오른쪽괄호", "_": "밑줄", "+": "더하기"}

getLogger("werkzeug").disabled = True

init()

app = Flask(__name__)

@app.route("/api/balance", methods=["POST"])
def balance():
    current_date = datetime.now().strftime("%B %d, %Y %H:%M:%S")
    current_time = time()
    req_data = request.get_json()
    id = req_data.get("id")
    pw = req_data.get("pw")
    token = req_data.get("token")
    account = accounts.get(id)
    accessToken = accessTokens.get(token)

    if not accessToken or accessToken.get("expirationDate") < current_time:
        print(f"{Fore.RED}{Style.BRIGHT}[UNAUTHORIZED] {token} | {request.remote_addr} | {current_date}{Style.RESET_ALL}")
        return {"result": False, "amount": 0, "reason": "Unauthorized", "timeout": round((time() - current_time) * 1000)}

    if not account:
        accounts[id] = {"pw": "", "keepLoginInfo": "", "userKey": 0, "phone": "", "token": token}
        account = accounts.get(id)
        #print(f"{Fore.RED}{Style.BRIGHT}[UNKNOWN] {id}:{pw} | {current_date}{Style.RESET_ALL}")
        #return {"result": False, "amount": 0, "reason": "아이디 등록 필요", "timeout": round((time() - current_time) * 1000)}

    if account.get("pw") != pw:
        accountData = fetchCookie(id, pw, current_date, current_time)
        if not accountData.get("result"):
            return accountData

    with httpx.Client() as client:
        keepLoginInfo = account.get("keepLoginInfo")
        client.cookies.set("KeepLoginConfig", parse.quote(keepLoginInfo))
        login_result = client.post("https://m.cultureland.co.kr/mmb/loginProcess.do", data={"keepLoginInfo": keepLoginInfo})

        if "frmRedirect" in login_result.text:
            print(f"{Fore.RED}{Style.BRIGHT}[LOGIN FAILED 1] {id}:{pw} | {current_date}{Style.RESET_ALL}")
            return {"result": False, "amount": 0, "reason": "아이디 또는 비밀번호 불일치 (1)", "timeout": round((time() - current_time) * 1000)}

        balance_result = client.get("https://m.cultureland.co.kr/tgl/getBalance.json").json()
        my_cash = balance_result.get("myCash")
        balance_time = round((time() - current_time) * 1000)

        print(f"{Fore.GREEN}{Style.BRIGHT}[BALANCE SUCCESS] {id} | {my_cash}원 | {balance_time}ms | {current_date}{Style.RESET_ALL}")
        return {"result": True, "amount": int(my_cash), "timeout": balance_time}

@app.route("/api/check", methods=["POST"])
def check():
    current_date = datetime.now().strftime("%B %d, %Y %H:%M:%S")
    current_time = time()
    req_data = request.get_json()
    token = req_data.get("token")
    accessToken = accessTokens.get(token)

    if not accessToken or accessToken.get("expirationDate") < current_time:
        print(f"{Fore.RED}{Style.BRIGHT}[UNAUTHORIZED] {token} | {request.remote_addr} | {current_date}{Style.RESET_ALL}")
        return {"result": False, "amount": 0, "reason": "Unauthorized", "timeout": round((time() - current_time) * 1000)}

    pin = req_data.get("pin").split("-")
    if len(pin) == 4:
        voucherData = httpx.post("https://www.cultureland.co.kr/voucher/getVoucherCheckMobileUsed.do", data={"code": "-".join(pin)}).json()
        resultCd = int(voucherData.get("resultCd"))
        resultMsg = voucherData.get("resultMsg")
        resultOther = voucherData.get("resultOther")

        if resultCd == 0:
            if len(resultOther) == 0:
                print(f"{Fore.CYAN}{Style.BRIGHT}[CHECK FAKE 1] {'-'.join(pin)} | 올바른 상품권 번호를 입력해 주세요 | {current_date}{Style.RESET_ALL}")
                return {"result": False, "amount": 0, "data": voucherData, "reason": "올바른 상품권 번호를 입력해 주세요", "timeout": round((time() - current_time) * 1000)}
            else:
                amount = resultOther[0].get("Balance")
                reason = "조회 완료" if bool(amount) else "잔액이 0원인 상품권"
                print(f"{Fore.GREEN}{Style.BRIGHT}[CHECK 0] {'-'.join(pin)} | {reason} | {current_date}{Style.RESET_ALL}")
                return {"result": bool(amount), "amount": amount, "data": voucherData, "reason": reason, "timeout": round((time() - current_time) * 1000)}
        elif resultCd == 1:
            print(f"{Fore.RED}{Style.BRIGHT}[CHECK ERROR] {'-'.join(pin)} | {resultMsg} | {current_date}{Style.RESET_ALL}")
            return {"result": False, "amount": 0, "data": voucherData, "reason": resultMsg, "timeout": round((time() - current_time) * 1000)}
        else:
            print(f"{Fore.RED}{Style.BRIGHT}[CHECK {resultCd}] {'-'.join(pin)} | Unknown Result Code | {current_date}{Style.RESET_ALL}")
            return {"result": False, "amount": 0, "data": voucherData, "reason": "Unknown Result Code " + resultCd, "timeout": round((time() - current_time) * 1000)}
    else:
        print(f"{Fore.CYAN}{Style.BRIGHT}[CHECK FAKE 2] {'-'.join(pin)} | {current_date}{Style.RESET_ALL}")
        return {"result": False, "amount": 0, "reason": "올바른 상품권 번호를 입력해 주세요", "timeout": randrange(50, 200)}

@app.route("/api/charge", methods=["POST"])
def charge():
    current_date = datetime.now().strftime("%B %d, %Y %H:%M:%S")
    current_time = time()
    req_data = request.get_json()
    id = req_data.get("id")
    pw = req_data.get("pw")
    token = req_data.get("token")
    account = accounts.get(id)
    accessToken = accessTokens.get(token)

    if not accessToken or accessToken.get("expirationDate") < current_time:
        print(f"{Fore.RED}{Style.BRIGHT}[UNAUTHORIZED] {token} | {request.remote_addr} | {current_date}{Style.RESET_ALL}")
        return {"result": False, "amount": 0, "reason": "Unauthorized", "timeout": round((time() - current_time) * 1000), "fake": False}

    if not account:
        accounts[id] = {"pw": "", "keepLoginInfo": "", "userKey": 0, "phone": "", "token": token}
        account = accounts.get(id)
        #print(f"{Fore.RED}{Style.BRIGHT}[UNKNOWN] {id}:{pw} | {current_date}{Style.RESET_ALL}")
        #return {"result": False, "amount": 0, "reason": "아이디 등록 필요", "timeout": round((time() - current_time) * 1000), "fake": False}

    if account.get("pw") != pw:
        accountData = fetchCookie(id, pw, current_date, current_time)
        if not accountData.get("result"):
            return accountData

    pin = req_data.get("pin").split("-")
    if len(pin) == 4 and len(pin[0]) == 4 and len(pin[1]) == 4 and len(pin[2]) == 4 and pin[0].isdigit() and pin[1].isdigit() and pin[2].isdigit() and pin[3].isdigit() and ((pin[0][:2] in ["20", "21", "22", "30", "31", "32", "40", "42", "51", "52"] and len(pin[3]) == 6) or (pin[0][:2] == "41" and pin[0][2:3] not in ["6", "8"] and len(pin[3]) == 6) or (pin[0][:3] in ["416", "418", "916"] and len(pin[3]) == 4)):
        with httpx.Client() as client:
            #mtk = mTransKey(client, "https://m.cultureland.co.kr/transkeyServlet")
            #pw_encrypt = mtk.new_keypad("qwerty", "passwd", "passwd", "password").encrypt_password(pw)

            #login_result = client.post("https://m.cultureland.co.kr/mmb/loginProcess.do", data={"userId": req_data.get("id"), "transkeyUuid": mtk.get_uuid(), "transkey_passwd": pw_encrypt, "transkey_HM_passwd": mtk.hmac_digest(pw_encrypt.encode())})

            if req_data.get("check") and len(pin[3]) == 4:
                voucherData = httpx.post("https://www.cultureland.co.kr/voucher/getVoucherCheckMobileUsed.do", data={"code": "-".join(pin)}).json()
                resultCd = int(voucherData.get("resultCd"))
                resultOther = voucherData.get("resultOther")

                charge_time = round((time() - current_time) * 1000)
                if resultCd == 0:
                    if len(resultOther) == 0:
                        print(f"{Fore.CYAN}{Style.BRIGHT}[FAKE 2] {id} | {'-'.join(pin)} | 0원 | 상품권 번호 불일치 | {charge_time}ms | {current_date}{Style.RESET_ALL}")
                        return {"result": False, "amount": 0, "reason": "상품권 번호 불일치", "timeout": charge_time, "fake": True}
                    else:
                        amount = resultOther[0].get("Balance")
                        if not bool(amount):
                            print(f"{Fore.CYAN}{Style.BRIGHT}[FAKE 3] {id} | {'-'.join(pin)} | 0원 | 잔액이 0원인 상품권 | {charge_time}ms | {current_date}{Style.RESET_ALL}")
                            return {"result": False, "amount": 0, "reason": "잔액이 0원인 상품권", "timeout": charge_time, "fake": True}
                elif resultCd != 1:
                    print(f"{Fore.RED}{Style.BRIGHT}[CHARGE FAIL {resultCd}] {id} | {'-'.join(pin)} | 0원 | Unknown Result Code | {charge_time}ms | {current_date}{Style.RESET_ALL}")
                    return {"result": False, "amount": 0, "reason": "Unknown Result Code " + resultCd, "timeout": charge_time, "fake": False}

            keepLoginInfo = account.get("keepLoginInfo")
            client.cookies.set("KeepLoginConfig", parse.quote(keepLoginInfo))
            login_result = client.post("https://m.cultureland.co.kr/mmb/loginProcess.do", data={"keepLoginInfo": keepLoginInfo})

            if "frmRedirect" in login_result.text:
                print(f"{Fore.RED}{Style.BRIGHT}[LOGIN FAILED 1] {id}:{pw} | {current_date}{Style.RESET_ALL}")
                return {"result": False, "amount": 0, "reason": "아이디 또는 비밀번호 불일치 (1)", "timeout": round((time() - current_time) * 1000), "fake": False}

            pageURL = "https://m.cultureland.co.kr/csh/cshGiftCard.do"
            if len(pin[3]) == 6:
                pageURL = "https://m.cultureland.co.kr/csh/cshGiftCardOnline.do"

            client.get(pageURL)

            mtk = mTransKey(client, "https://m.cultureland.co.kr/transkeyServlet")
            pin_encrypt = mtk.new_keypad("number", "txtScr14", "scr14", "password").encrypt_password(pin[3])

            chargeURL = "https://m.cultureland.co.kr/csh/cshGiftCardProcess.do"
            if len(pin[3]) == 6:
                chargeURL = "https://m.cultureland.co.kr/csh/cshGiftCardOnlineProcess.do"

            client.post(chargeURL, data={"scr11": pin[0], "scr12": pin[1], "scr13": pin[2], "transkeyUuid": mtk.get_uuid(), "transkey_txtScr14": pin_encrypt, "transkey_HM_txtScr14": mtk.hmac_digest(pin_encrypt.encode())})
            charge_result = client.get("https://m.cultureland.co.kr/csh/cshGiftCardCfrm.do")

            charge_amount = charge_result.text.split('walletChargeAmt" value="')[1].split("\n\n\n")[0]
            wallet_charge_amount = int(charge_amount.split('"')[0])
            charge_amount = wallet_charge_amount + int(charge_amount.split('value="')[1].split('"')[0])

            charge_result = charge_result.text.split("<b>")[1].split("</b>")[0]
            if wallet_charge_amount:
                charge_result = charge_result.split(">")[1].split("<")[0]

            charge_time = round((time() - current_time) * 1000)
            if bool(charge_amount):
                print(f"{Fore.GREEN}{Style.BRIGHT}[CHARGE SUCCESS] {id} | {'-'.join(pin)} | {charge_amount}원 | {charge_result} | {charge_time}ms | {current_date}{Style.RESET_ALL}")
            else:
                print(f"{Fore.CYAN}{Style.BRIGHT}[CHARGE FAILED] {id} | {'-'.join(pin)} | {charge_amount}원 | {charge_result} | {charge_time}ms | {current_date}{Style.RESET_ALL}")
            return {"result": bool(charge_amount), "amount": charge_amount, "reason": charge_result, "timeout": charge_time, "fake": False}
    else:
        print(f"{Fore.CYAN}{Style.BRIGHT}[FAKE 1] {id} | {'-'.join(pin)} | 0원 | 상품권 번호 불일치 | -1ms | {current_date}{Style.RESET_ALL}")
        return {"result": False, "amount": 0, "reason": "상품권 번호 불일치", "timeout": randrange(400, 500), "fake": True}

@app.route("/api/gift", methods=["POST"])
def gift():
    current_date = datetime.now().strftime("%B %d, %Y %H:%M:%S")
    current_time = time()
    req_data = request.get_json()
    id = req_data.get("id")
    pw = req_data.get("pw")
    amount = req_data.get("amount")
    token = req_data.get("token")
    account = accounts.get(id)
    accessToken = accessTokens.get(token)

    if not accessToken or accessToken.get("expirationDate") < current_time:
        print(f"{Fore.RED}{Style.BRIGHT}[UNAUTHORIZED] {token} | {request.remote_addr} | {current_date}{Style.RESET_ALL}")
        return {"result": False, "amount": 0, "reason": "Unauthorized", "timeout": round((time() - current_time) * 1000), "fake": False}

    if not account:
        accounts[id] = {"pw": "", "keepLoginInfo": "", "userKey": 0, "phone": "", "token": token}
        account = accounts.get(id)
        #print(f"{Fore.RED}{Style.BRIGHT}[UNKNOWN] {id}:{pw} | {current_date}{Style.RESET_ALL}")
        #return {"result": False, "amount": 0, "reason": "아이디 등록 필요", "timeout": round((time() - current_time) * 1000), "fake": False}

    if account.get("pw") != pw:
        accountData = fetchCookie(id, pw, current_date, current_time)
        if not accountData.get("result"):
            return accountData

    with httpx.Client() as client:
        keepLoginInfo = account.get("keepLoginInfo")
        client.cookies.set("KeepLoginConfig", parse.quote(keepLoginInfo))
        login_result = client.post("https://m.cultureland.co.kr/mmb/loginProcess.do", data={"keepLoginInfo": keepLoginInfo})

        if "frmRedirect" in login_result.text:
            print(f"{Fore.RED}{Style.BRIGHT}[LOGIN FAILED 1] {id}:{pw} | {current_date}{Style.RESET_ALL}")
            return {"result": False, "amount": 0, "reason": "아이디 또는 비밀번호 불일치 (1)", "timeout": round((time() - current_time) * 1000)}

        client.get("https://m.cultureland.co.kr/gft/gftPhoneApp.do")

        client.post("https://m.cultureland.co.kr/gft/gftPhoneCashProc.do", data={"revEmail": "", "sendType": "S", "userKey": account.get("userKey"), "limitGiftBank": "N", "giftCategory": "M", "amount": amount, "quantity": 1, "revPhone": account.get("phone").replace("-", ""), "sendTitl": "", "paymentType": "cash"})
        gift_result = client.get("https://m.cultureland.co.kr/gft/gftPhoneCfrm.do").text

        if '<p>선물(구매)하신 <strong class="point">모바일문화상품권</strong>을<br /><strong class="point">요청하신 정보로 전송</strong>하였습니다.</p>' not in gift_result:
            print(f"{Fore.CYAN}{Style.BRIGHT}[GIFT FAILED] {id} | {amount}원 | {current_date}{Style.RESET_ALL}")
            return {"result": False, "amount": 0, "reason": "선물(구매)가 실패하였습니다", "timeout": round((time() - current_time) * 1000)}

        gift_result = gift_result.split("- 상품권 바로 충전 : https://m.cultureland.co.kr/csh/dc.do?code=")[1].split("&lt;br&gt;")

        gift_code = gift_result[0]
        gift_pin = gift_result[8].replace("- 바코드번호 : ", "")

        gift_time = round((time() - current_time) * 1000)
        print(f"{Fore.GREEN}{Style.BRIGHT}[GIFT SUCCESS] {id} | {amount}원 | {gift_pin} | {gift_time}ms | {current_date}{Style.RESET_ALL}")
        return {"result": True, "amount": int(amount), "reason": "선물(구매)하신 모바일문화상품권을 요청하신 정보로 전송하였습니다", "data": {"code": gift_code, "pin": gift_pin}, "timeout": gift_time}

def fetchCookie(id, pw, current_date, current_time):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("https://m.cultureland.co.kr/mmb/loginMain.do", wait_until="commit")

        with page.expect_response(compile("https:\/\/m\.cultureland\.co\.kr\/botdetectcaptcha\?get=image&c=cultureCaptcha&t=*")) as resp:
            captchaTask = httpx.post("http://2captcha.com/in.php?key=f54b2ff707c7fd6ba3b960ac37b6c004&method=post", files={"file": resp.value.body()}).text.split("|")
            taskId = captchaTask[1]
            if captchaTask[0] != "OK":
                print(f"{Fore.RED}{Style.BRIGHT}[CAPTCHA FAILED 1] {id}:{pw} | {captchaTask[0]} | {current_date}{Style.RESET_ALL}")
                return {"result": False, "amount": 0, "reason": "로그인 캡챠 실패 (1)", "timeout": round((time() - current_time) * 1000), "fake": False}

        page.fill("#txtUserId", id)
        page.click("#passwd")

        charIndex = 0
        for char in pw:
            if char.isupper():
                page.click("[alt='쉬프트']")
                page.click(f"[alt='대문자{char}']")
                if charIndex < 11:
                    page.click("[alt='쉬프트']")
            elif char.isalpha() or char.isdigit():
                page.click(f"[alt='{char}']")
            elif char in altChars.keys():
                page.click("[alt='특수키']")
                page.click(f"[alt='{altChars.get(char)}']")
                if charIndex < 11:
                    page.click("[alt='특수키']")
            else:
                print(f"{Fore.RED}{Style.BRIGHT}[UNKNOWN CHAR {char}] {id}:{pw} | {current_date}{Style.RESET_ALL}")
                return {"result": False, "amount": 0, "reason": "아이디 또는 비밀번호 불일치 (3)", "timeout": round((time() - current_time) * 1000), "fake": False}

            charIndex += 1

        if len(pw) < 12:
            page.click("[alt='입력완료']")
        page.click("#chkKeepLogin")

        captchaTask = httpx.get("http://2captcha.com/res.php?key=f54b2ff707c7fd6ba3b960ac37b6c004&action=get&id=" + taskId).text
        while captchaTask == "CAPCHA_NOT_READY":
            sleep(5)
            captchaTask = httpx.get("http://2captcha.com/res.php?key=f54b2ff707c7fd6ba3b960ac37b6c004&action=get&id=" + taskId).text

        captchaTask = captchaTask.split("|")
        if captchaTask[0] != "OK":
            print(f"{Fore.RED}{Style.BRIGHT}[CAPTCHA FAILED 2] {id}:{pw} | {captchaTask[0]} | {current_date}{Style.RESET_ALL}")
            return {"result": False, "amount": 0, "reason": "로그인 캡챠 실패 (2)", "timeout": round((time() - current_time) * 1000), "fake": False}

        page.type("#captchaCode", captchaTask[1].upper())
        page.click("#btnLogin", no_wait_after=True)

        with page.expect_response("https://m.cultureland.co.kr/mmb/loginProcess.do") as resp:
            if resp.value.status != 302:
                print(f"{Fore.RED}{Style.BRIGHT}[LOGIN FAILED 2] {id}:{pw} | {current_date}{Style.RESET_ALL}")
                return {"result": False, "amount": 0, "reason": "아이디 또는 비밀번호 불일치 (2)", "timeout": round((time() - current_time) * 1000), "fake": False}

            responseCookies = resp.value.all_headers().get("set-cookie")
            keepLoginInfo = parse.unquote(responseCookies.split("KeepLoginConfig=")[1].split(";")[0])
            sessionId = responseCookies.split("JSESSIONID=")[1].split(";")[0]

        browser.close()

        accountData = httpx.post("https://m.cultureland.co.kr/tgl/flagSecCash.json", cookies={"JSESSIONID": sessionId}).json()

        _phoneNumber = accountData.get("Phone")
        phoneNumber = ""
        if _phoneNumber:
            for i in range(0, len(_phoneNumber)):
                if i == 3 or i == 7:
                    phoneNumber += "-"
                phoneNumber += _phoneNumber[i]

        accounts[id]["pw"] = pw
        accounts[id]["keepLoginInfo"] = keepLoginInfo
        accounts[id]["userKey"] = int(accountData.get("userKey"))
        accounts[id]["phone"] = phoneNumber

        with open("accounts.json", "w") as f:
            dump(accounts, f, indent=4)

        return {"result": True}

app.run(host="0.0.0.0", port=9999)
