PID_DIRECTORY := .run
BACKEND_PORT := 8000
BACKEND_PID_FILE := $(PID_DIRECTORY)/backend.pid
FRONTEND_PID_FILE := $(PID_DIRECTORY)/frontend.pid

.PHONY: backend-up backend-down frontend-up frontend-down

backend-up:
	@mkdir -p $(PID_DIRECTORY)
	@if [ -f $(BACKEND_PID_FILE) ] && kill -0 $$(cat $(BACKEND_PID_FILE)) 2>/dev/null; then \
		echo "백엔드가 이미 실행 중입니다."; \
	else \
		rm -f $(BACKEND_PID_FILE); \
		if [ -f .env ]; then set -a; . ./.env; set +a; fi; \
		if [ -z "$$DATABASE_URL" ]; then echo "DATABASE_URL을 .env 또는 환경 변수에 설정해 주세요."; exit 1; fi; \
		nohup .venv/bin/uvicorn backend.app.main:app --port $(BACKEND_PORT) > $(PID_DIRECTORY)/backend.log 2>&1 & echo $$! > $(BACKEND_PID_FILE); \
		echo "백엔드를 시작했습니다: http://127.0.0.1:$(BACKEND_PORT)"; \
	fi

backend-down:
	@pids="$$(lsof -tiTCP:$(BACKEND_PORT) -sTCP:LISTEN)"; \
	if [ -n "$$pids" ]; then \
		if kill $$pids; then echo "백엔드를 종료했습니다."; else echo "백엔드를 종료하지 못했습니다." >&2; exit 1; fi; \
	else echo "백엔드는 실행 중이 아닙니다."; fi; \
	rm -f $(BACKEND_PID_FILE)

frontend-up:
	@mkdir -p $(PID_DIRECTORY)
	@if [ -f $(FRONTEND_PID_FILE) ] && kill -0 $$(cat $(FRONTEND_PID_FILE)) 2>/dev/null; then \
		echo "프런트엔드가 이미 실행 중입니다."; \
	else \
		rm -f $(FRONTEND_PID_FILE); \
		nohup npm --prefix frontend run dev -- --host 127.0.0.1 > $(PID_DIRECTORY)/frontend.log 2>&1 & echo $$! > $(FRONTEND_PID_FILE); \
		echo "프런트엔드를 시작했습니다: http://127.0.0.1:5173"; \
	fi

frontend-down:
	@if [ ! -f $(FRONTEND_PID_FILE) ]; then \
		echo "프런트엔드는 실행 중이 아닙니다."; \
	else \
		pid=$$(cat $(FRONTEND_PID_FILE)); \
		if kill -0 $$pid 2>/dev/null; then kill $$pid; echo "프런트엔드를 종료했습니다."; else echo "프런트엔드는 이미 종료되었습니다."; fi; \
		rm -f $(FRONTEND_PID_FILE); \
	fi
