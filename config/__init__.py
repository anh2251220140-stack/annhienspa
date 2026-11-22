try:
    import MySQLdb
except ModuleNotFoundError as exc:
    if exc.name != "MySQLdb":
        raise
    # Serverless builds use PyMySQL's supported MySQLdb compatibility layer.
    import pymysql

    pymysql.install_as_MySQLdb()
