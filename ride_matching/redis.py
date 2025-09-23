import redis



class redistester:
    redis_client = redis.StrictRedis(
        host='172.17.83.139',
        port=6379,
        db=0,
        decode_responses=True
    )

    @staticmethod
    def pingredis():
         if redistester.redis_client.ping():
             print('Pong!')
         else:
             print('Connection fariled.')

