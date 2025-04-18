import time, logging, functools

def with_retry(func=None, *, max_retries=3, initial_delay=5):
    if func is None:
        return lambda f: with_retry(f, max_retries=max_retries, initial_delay=initial_delay)
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        retries = 0
        delay = initial_delay
        while retries < max_retries:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logging.warning("Erro em %s: %s. Retry %s/%s", func.__name__, e, retries+1, max_retries)
                time.sleep(delay)
                delay *= 2
                retries += 1
        raise Exception(f"Falha persistente em {func.__name__}")
    return wrapper