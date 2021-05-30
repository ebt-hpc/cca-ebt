#!/usr/bin/env python3

from pymongo import MongoClient

if __name__ == '__main__':
    cli = MongoClient('localhost', 27017)
    db = cli.admin
    try:
        db.command('shutdown')
    except:
        pass
