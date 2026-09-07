from upstash_redis import Redis

redis = Redis(url="https://optimal-civet-69003.upstash.io", token="gQAAAAAAAQ2LAAIgcDI4MTIwM2M4MGMwYmI0yczUzYjBmYjQ0MDg3YTY0ZTYyYg")

redis.set("foo", "bar")
value = redis.get("foo")
print("Retrieved from Upstash:", value)
