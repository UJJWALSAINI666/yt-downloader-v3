import multiprocessing, os
bind = f"0.0.0.0:{os.environ.get('PORT','8000')}"
workers = 2
threads = 8
timeout = 360
keepalive = 60
accesslog = "-"
errorlog = "-"
