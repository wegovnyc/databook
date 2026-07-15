import os
import hashlib
import datetime
from config import Config
from postgrex import PostgresModel
from fastapi_login import LoginManager


class User:
    __model = None
    __scdict = {'read': ['read'], 'full': ['read', 'write']}
        

    
    def __init__(self):
        self.__model = PostgresModel()
        self.__mng = LoginManager(Config.fastapi['key'], '/login')
        
    def create(self):
        hint = 'Email: '
        for _ in range(3):
            email = input(hint)
            if email:
                break
            hint = 'Please enter valid email: '
        else:
            return None
                
        user = self.get_user(email=email)
        if user:
            return 'user exists'
                
        hint = 'Password: '
        for _ in range(3):
            pwd = input(hint)
            if pwd:
                break
            hint = 'Please enter password: '
        else:
            return None
                
        hint = 'Repeat password: '
        for _ in range(3):
            pwd2 = input(hint)
            if pwd2 == pwd:
                break
            if not pwd2:
                hint = 'Please repeat password: '
            else:
                hint = 'Password does not match: '
        else:
            return None
                
        for _ in range(3):
            sc = input('1-Read only, 2-Full access (1): ')
            if sc in ['1', '2', '']:
                scope = {'1': 'read', '2': 'full', '': 'read'}[sc]
                break
        else:
            return None
            
        id = self.gen_id()
        
        self.__model.q("INSERT INTO users (id, email, pwdhash, scope) VALUES ('{}', '{}', '{}', '{}')".format(id, email, __class__.pwd_hash(pwd), scope))
        
        return self.newapikey(email)
        
    def delete(self):
        hint = 'Email: '
        for _ in range(3):
            email = input(hint)
            if email:
                break
            hint = 'Please enter valid email: '
        else:
            return None
                
        user = self.get_user(email=email)
        if not user:
            return 'User not found'
        self.__model.q("DELETE FROM users WHERE email='{}'".format(email))
    
    def newemail(self):
        hint = 'Email: '
        for _ in range(3):
            email = input(hint)
            if email:
                break
            hint = 'Please enter valid email: '
        else:
            return None
                
        user = self.get_user(email=email)
        if not user:
            return 'User not found'

        hint = 'New email: '
        for _ in range(3):
            newemail = input(hint)
            if newemail:
                break
            hint = 'Please enter new email: '
        else:
            return None
                
        hint = 'Repeat email: '
        for _ in range(3):
            newemail2 = input(hint)
            if newemail2 == newemail:
                break
            if not newemail2:
                hint = 'Please repeat email: '
            else:
                hint = 'Email does not match: '
        else:
            return None
                
        self.__model.q("UPDATE users SET email='{}' WHERE email='{}'".format(newemail, email))

    
    def newpassword(self):
        hint = 'Email: '
        for _ in range(3):
            email = input(hint)
            if email:
                break
            hint = 'Please enter valid email: '
        else:
            return None
                
        user = self.get_user(email=email)
        if not user:
            return 'User not found'

        hint = 'New password: '
        for _ in range(3):
            pwd = input(hint)
            if pwd:
                break
            hint = 'Please enter new password: '
        else:
            return None
                
        hint = 'Repeat password: '
        for _ in range(3):
            pwd2 = input(hint)
            if pwd2 == pwd:
                break
            if not pwd2:
                hint = 'Please repeat password: '
            else:
                hint = 'Password does not match: '
        else:
            return None
                
        self.__model.q("UPDATE users SET pwdhash='{}' WHERE email='{}'".format(__class__.pwd_hash(pwd), email))
    
    def newapikey(self, email=None):
        hint = 'Email: '
        if not email:
            for _ in range(3):
                email = input(hint)
                if not email:
                    hint = 'Please enter valid email: '
                    continue
                user = self.get_user(email=email)
                if user:
                    break
                hint = 'User not found. Please try again. Email: '
            else:
                return 'User not found'
        else:
            user = self.get_user(email=email)
            if not user:
                return 'User not found'
                
        token = self.__mng.create_access_token(
            data={'sub': user['id']},
            expires=datetime.timedelta(days=730),
            scopes=self.__scdict[user['scope']]
        )
        return 'Please save following API key. It will not be available later and can be only regenerated with user:newapikey command:\n{}'.format(token)
       
# ==== _ in proc name makes it not callable via manager ========================================================================
       
    def get_user(self, id=None, email=None):
        #with open(r'c:\OSPanel\domains\DevinBalkind\openReferral\hsds2.1\api\_docs\fastapi2\log', 'w') as f:
        #    f.write('{} {}'.format(id, email))
        if id==None and email==None:
            return None
        sql = "SELECT id, email, pwdhash, scope FROM users WHERE {}='{}'"
        return self.__model.select(sql.format('email', email) if not id else sql.format('id', id), 0)

    def auth_user(self, email, pwd):
        sql = "SELECT id, email, scope FROM users WHERE email='{}' AND pwdhash='{}'".format(email, __class__.pwd_hash(pwd))
        return self.__model.select(sql, 0, True)
        
    def gen_id(self):
        return os.urandom(10).hex()
        
    def pwd_hash(pwd):
        return hashlib.sha256(pwd.encode()).hexdigest()
