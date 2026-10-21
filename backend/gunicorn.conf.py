"""Gunicorn settings for the deployed app (see ../Dockerfile and ../fly.toml).

Exactly one process: the weather budget and the caches live in its memory, so a second process
would have its own counts and the free weather tier's limits would no longer hold. Threads give
concurrency inside that one process; a request waiting for the next minute of weather allowance
sleeps without holding up the others.
"""

bind = "0.0.0.0:8000"
workers = 1
threads = 8
# Planning a long trip can take ~20 s of routing plus up to ~65 s waiting for weather allowance.
timeout = 120
accesslog = "-"
