# coding=utf8

import os
import sys
import logging
logging.basicConfig(level=logging.INFO)

import toml

sys.path.insert(0, '..')
from skylark import Database, database, DBAPI_MAPPINGS, DatabaseType,\
    Model

from models import User, Post


dbapi_name = os.environ.get('DBAPI', 'MySQLdb')
dbapi = __import__(dbapi_name)
configs = toml.loads(open('conf.toml').read())[dbapi_name]

db_type_mappings = {
    'pymysql': 'mysql',
    'MySQLdb': 'mysql',
    'sqlite3': 'sqlite',
}

db_type = db_type_mappings[dbapi_name]

user_sql = open('%s.user.sql' % db_type).read()
post_sql = open('%s.post.sql' % db_type).read()


database.set_dbapi(dbapi)
database.config(**configs)
database.set_autocommit(True)


class Test(object):

    def setUp(self):
        database.execute(user_sql)
        database.execute(post_sql)

    def tearDown(self):
        database.execute("drop table t_post")
        database.execute("drop table t_user")


class TestDatabase_:

    def setUp(self):
        self.database = DatabaseType()

    def test_alias(self):
        assert database is Database

    def __shouldnt_import(self, name):
        try:
            __import__(name)
            raise Exception
        except ImportError:
            pass

    def test_init(self):
        assert self.database.conn is None
        assert self.database.configs == {}
        assert self.database.dbapi.module.__name__ in DBAPI_MAPPINGS

        # test load orders
        name = self.database.dbapi.module.__name__

        if name == 'MySQLdb':
            assert __import__('MySQLdb')
        elif name == 'pymysql':
            assert __import__('pymysql')
            self.__shouldnt_import('MySQLdb')
        elif name == 'sqlite3':
            assert __import__('sqlite3')
            self.__shouldnt_import('MySQLdb')
            self.__shouldnt_import('pymysql')

    def test_set_dbapi(self):
        self.database.set_dbapi(dbapi)
        assert self.database.dbapi.module.__name__ == dbapi_name


class TestDatabase(Test):

    def setUp(self):
        self.database = DatabaseType()
        self.database.set_dbapi(dbapi)
        super(TestDatabase, self).setUp()

    def test_config(self):
        assert self.database.configs == {}
        self.database.config(**configs)
        assert self.database.configs
        assert not self.database.conn
        self.database.connect()
        assert self.database.conn
        self.database.config(**configs)
        assert not self.database.dbapi.conn_is_open(self.database.conn)

    def test_connect(self):
        assert self.database.conn is None
        self.database.config(**configs)
        conn1 = self.database.connect()
        conn2 = self.database.connect()
        assert conn1 is not conn2
        assert self.database.dbapi.conn_is_open(conn1)
        assert self.database.dbapi.conn_is_open(conn2)

    def test_get_conn(self):
        assert self.database.conn is None
        self.database.config(**configs)
        conn = self.database.get_conn()
        assert conn and self.database.dbapi.conn_is_open(conn)
        assert conn and self.database.dbapi.conn_is_alive(conn)
        conn1 = self.database.get_conn()
        assert conn1 is conn

    def test___del__(self):
        self.database.config(**configs)
        self.database.connect()
        conn = self.database.conn
        dbapi = self.database.dbapi
        del self.database
        assert not dbapi.conn_is_open(conn)

    def test_execute(self):
        self.database.config(**configs)
        cursor = self.database.execute(
            "insert into t_user (name, email) values ('jack', 'i@gmail.com')")
        assert cursor.lastrowid == 1

    def test_execute_sql(self):
        pass

    def change(self):
        self.database.configs(**configs)
        self.database.connect()
        old_conn = self.database.conn
        self.database.execute('create database skylarktests2')
        self.database.change('skylarktests2')
        assert self.database.configs != configs
        if db_type == 'mysql':
            self.database.conn is old_conn
        else:
            self.database.conn is not old_conn
            assert not self.database.dbapi.conn_is_open(old_conn)

    def test_transaction(self):
        db = self.database
        db.config(**configs)
        db.execute("insert into t_user (name, email) values ('j', 'j@i.com')")
        db.set_autocommit(False)
        t = db.transaction()
        try:
            db.execute("insert into t_user set x;")  # syntax error
        except Exception:
            t.rollback()
        else:
            raise Exception
        cursor = db.execute('select count(*) from t_user;')
        db.conn.commit()  # !important
        assert cursor.fetchone()[0] == 1

        with db.transaction() as t:
            db.execute(
                "insert into t_user (name, email) values ('a', 'a@b.com')")
            db.execute(
                "insert into t_user (name, email) values ('a', 'a@b.com')")
        cursor = db.execute('select count(*) from t_user')
        db.commit()
        assert cursor.fetchone()[0] == 3


class TestField_:

    def test_name(self):
        assert User.name.name == 'name'
        assert User.email.name == 'email'
        assert Post.name.name == 'name'
        assert Post.user_id.name == 'user_id'

    def test_fullname(self):
        assert User.name.fullname == 't_user.name'
        assert User.email.fullname == 't_user.email'
        assert Post.name.fullname == 't_post.name'
        assert Post.user_id.fullname == 't_post.user_id'

    def test_model(self):
        assert User.id.model is User
        assert User.name.model is User
        assert User.email.model is User
        assert Post.name.model is Post
        assert Post.user_id.model is Post

    def test_alias(self):
        fd = User.id.alias('user_id')
        assert fd.name == 'user_id'
        assert fd.inst is User.id


class TestPrimaryKey_:

    def test_is_primarykey(self):
        assert User.id.is_primarykey is True
        assert User.name.is_primarykey is False
        assert User.email.is_primarykey is False
        assert Post.post_id.is_primarykey is True
        assert Post.user_id.is_primarykey is False
        assert Post.name.is_primarykey is False


class TestForeignKey_:

    def test_is_foreignkey(self):
        assert User.id.is_foreignkey is False
        assert User.name.is_foreignkey is False
        assert User.email.is_foreignkey is False
        assert Post.post_id.is_foreignkey is False
        assert Post.name.is_foreignkey is False
        assert Post.user_id.is_foreignkey is True


class TestAlias_:

    def setUp(self):
        self._alias = User.name.alias('username')

    def test_name(self):
        assert self._alias.name == 'username'

    def test_inst(self):
        assert self._alias.inst is User.name


class TestModel_:

    def test_table_name(self):
        class MyModel(Model):
            pass
        assert MyModel.table_name == 'my_model'

        class Member(Model):
            pass
        assert Member.table_name == 'member'

        class Cat(Model):
            table_name = 'cute_cat'
        assert Cat.table_name == 'cute_cat'

    def test_table_prefix(self):
        class Users(Model):
            table_prefix = 't_'
        assert Users.table_name == 't_users'

        class CuteDog(Model):
            table_prefix = 'dd_'
        assert CuteDog.table_name == 'dd_cute_dog'

        class Dog(Model):
            table_name = 'custom_table_name'
            table_prefix = 'd_'
        assert Dog.table_name == 'd_custom_table_name'

    def test_table_prefix_is_inheritable(self):
        class X(Model):
            table_prefix = 't_'

        class A(X):
            pass

        class B(X):
            pass

        assert A.table_prefix is X.table_prefix
        assert B.table_prefix is X.table_prefix
        assert A.table_name == 't_a'
        assert B.table_name == 't_b'

    def test_primarykey(self):
        assert User.primarykey is User.id
        assert Post.primarykey is Post.post_id

    def test_fields(self):
        field_names = set(User.fields.keys())
        _field_names = set(('id', 'name', 'email'))
        assert field_names == _field_names
        field_names = set(Post.fields.keys())
        _field_names = set(('post_id', 'name', 'user_id'))
        assert field_names == _field_names


class TestModel(Test):

    def test_insert(self):
        query = User.insert(name='jack', email='jack@gmail.com')
        assert query.execute() == 1
        assert User.count() == 1
        user = User.getone()
        assert user.name == 'jack' and user.email == 'jack@gmail.com'

    def test_update(self):
        user = User.create(name='jack', email='jack@gmail.com')
        assert user.id == 1
        assert user.name == 'jack'
        assert user.email == 'jack@gmail.com'
        assert User.count() == 1

        query = User.at(1).update(email='jack@g.com')
        rows_affected = query.execute()
        assert rows_affected == 1
        user = User.getone()
        assert user.id == 1 and user.email == 'jack@g.com'

    def test_inst_in_model(self):
        user = User.create(name='jack', email='jack@gmail.com')

        # inst with `_in_db=True` won't call db to run a query
        database.conn.close()  # close conn to test if any sql was executed
        database.conn = None
        assert user in User
        assert database.conn is None

        # inst without `_in_db=True` call a query
        assert User(name='amy') not in User
        assert database.conn is not None

    def test_select(self):
        User.create(name='jack', email='jack@gmail.com')
        User.create(name='amy', email='amy@gmail.com')
        User.create(name='tom', email='tom@gmail.com')
        ### select all fields
        query = User.select()
        result = query.execute()
        assert result.count == 3
        for user in result.all():
            assert '%s@gmail.com' % user.name == user.email
        ### select part fields
        query = User.select(User.name)
        result = query.execute()
        assert result.count == 3
        jack = result.one()
        assert jack.name == 'jack'
        amy = result.one()
        assert amy.name == 'amy'
        tom = result.one()
        assert tom.name == 'tom'
        assert result.one() is None
        ### select with where
        query = User.where(name='jack').select()
        result = query.execute()
        assert result.count == 1
        assert result.one().name == 'jack'

    def test_delete(self):
        User.create(name='jack', email='jack@gmail.com')
        User.create(name='amy', email='amy@gmail.com')
        query = User.at(3).delete()
        rows_affected = query.execute()
        assert rows_affected == 0
        query = User.at(1).delete()
        rows_affected = query.execute()
        assert rows_affected == 1
        assert User.count() == 1

    def test_create(self):
        user = User.create(name='jack', email='jack@gmail.com')
        assert user.data == {
            'name': 'jack', 'email': 'jack@gmail.com', 'id': 1
        }
        assert user in User


class TestSelectResult(Test):

    def test_count(self):
        pass

    def test_one(self):
        pass

    def test_tuples(self):
        pass
