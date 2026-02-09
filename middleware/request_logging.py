import time
import json
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.concurrency import iterate_in_threadpool
from services.logger_service import LoggerService

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # --- LOG INPUT ---
        body = await request.body()
        input_data = ""
        try:
            if body:
                json_body = json.loads(body)
                input_data = json.dumps(json_body, indent=2)
            else:
                input_data = "[Empty Body]"
        except:
            input_data = body.decode('utf-8', errors='ignore')[:1000] # Truncate if binary/large

        print(f"\n🔵 [INPUT] {request.method} {request.url.path}")
        if input_data and input_data != "[Empty Body]":
             print(f"{input_data}\n")

        # Re-inject body for next handlers (since we consumed it)
        # FastAPI/Starlette consumes stream, so we must replenish it
        # Actually, for standard Middleware, consuming request.body() is risky.
        # A safer way in FastAPI is to use a dependency or just log what we can without consuming stream if possible.
        # But to see "Input", we MUST read body.
        # Workaround: Custom receive wrapper? Or just use "Receive" in standard ASGI middleware?
        # BaseHTTPMiddleware makes this hard.
        # Let's try a simpler approach: Log only JSON bodies if possible, or assume lightweight.
        # To avoid breaking stream:
        
        async def receive_wrapper():
            return {"type": "http.request", "body": body, "more_body": False}
        
        # Hacky rewrite of request receive to allow downstream to read again
        request._receive = receive_wrapper

        # --- PROCESS ---
        try:
            response = await call_next(request)
        except Exception as e:
            print(f"🔴 [ERROR] {request.url.path}: {str(e)}")
            raise e

        process_time = (time.time() - start_time) * 1000
        
        # --- LOG OUTPUT ---
        # Capturing response body in Middleware is also tricky with StreamingResponse.
        # We will log status code and time. 
        # For "Output" content, capturing response body requires wrapping response iterator.
        
        response_body = [section async for section in response.body_iterator]
        
        # Re-create async iterator for the response
        async def new_body_iterator():
            for chunk in response_body:
                yield chunk
        
        response.body_iterator = new_body_iterator()
        
        output_data = ""
        try:
            if response_body:
                # Join bytes
                full_body = b''.join(response_body)
                json_resp = json.loads(full_body)
                output_data = json.dumps(json_resp, indent=2)
            else:
                output_data = "[Empty Response]"
        except:
            output_data = "[Binary/Non-JSON Response]"

        print(f"🟢 [OUTPUT] {response.status_code} ({process_time:.2f}ms)")
        if output_data and output_data != "[Binary/Non-JSON Response]":
             print(f"{output_data}\n")
        
        return response
