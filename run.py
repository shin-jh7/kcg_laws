import os
import sys
import time
import socket
import subprocess
import webbrowser
import uvicorn

PORT = 8000
HOST = "127.0.0.1"

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0

def kill_process_on_port(port: int):
    """Windows 환경에서 특정 포트를 점유 중인 프로세스를 찾아 안전하게 종료합니다."""
    try:
        # netstat으로 점유 중인 PID 확인
        cmd = f'netstat -ano | findstr :{port}'
        output = subprocess.check_output(cmd, shell=True).decode("cp949", errors="ignore")
        pids = set()
        for line in output.strip().splitlines():
            parts = line.split()
            if len(parts) >= 5 and "LISTENING" in line:
                pid = parts[-1]
                if pid.isdigit() and int(pid) != os.getpid():
                    pids.add(pid)
                    
        for pid in pids:
            print(f"[알림] 포트 {port}를 점유 중인 기존 프로세스(PID: {pid})를 정리합니다...")
            subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.5)
    except Exception as e:
        pass

def main():
    print("=" * 65)
    print("      [해양경찰 법령정보센터] 로컬 서버 구동기")
    print("=" * 65)
    print()

    # 1. 포트 충돌 자동 점검 및 해제
    if is_port_in_use(PORT, HOST):
        print(f"[점검] {PORT}번 포트가 이미 사용 중입니다. 기존 프로세스를 자동 정리합니다...")
        kill_process_on_port(PORT)
        time.sleep(1)

    # 2. 브라우저 자동 오픈
    def open_browser():
        time.sleep(1.2)
        url = f"http://{HOST}:{PORT}"
        print(f"[접속] 브라우저를 엽니다: {url}")
        webbrowser.open(url)

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    print(f"[실행] 서버를 시작합니다 -> http://{HOST}:{PORT}")
    print("       서버를 종료하려면 이 창에서 Ctrl + C를 누르세요.")
    print("=" * 65)
    print()

    # 3. Uvicorn 서버 실행
    uvicorn.run("server.main:app", host=HOST, port=PORT, reload=False, log_level="info")

if __name__ == "__main__":
    main()
