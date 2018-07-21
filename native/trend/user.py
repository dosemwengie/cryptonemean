import redis

#username, strategy, amount, goal, list of coins


class User():
    def __init__(self, name, strategy, goal, coins):
        self.name = name
        self.strategy = strategy
        self.goal = goal
        self.coins = coins
        self.redis = redis.Redis()

    def get_user(self, user):
        key = ':'.join(["user",user])
        value = self.redis.hgetall(key)
        if not value:
            raise UserNotExists("Not such user")
        return value

    def set_user(self, user, changes={}):
        mapping = {'name': changes.get('name', self.name),
                    'strategy': changes.get('strategy', self.strategy),
                    'goal': changes.get('goal', self.goal),
                    'coins': changes.get('coins', self.coins)
                    }
        key = ':'.join(['user',user])
        self.redis.hmset(key, mapping)


class UserNotExists(Exception):
    pass
