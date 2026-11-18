"""本地数据库迁移和交互式账号初始化，不接受命令行明文密码。"""

import argparse
from getpass import getpass
from pathlib import Path

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.schemas import LoginName
from app.domain.enums import Role
from app.repositories.database import get_engine
from app.repositories.models import AppUser
from app.services.auth import hash_password


def migration_config():
    backend = Path(__file__).resolve().parents[1]
    return Config(str(backend / "alembic.ini"))


def upgrade_database(engine):
    config = migration_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def create_user(db: Session, login: str, password: str, role: Role):
    login = TypeAdapter(LoginName).validate_python(login)
    if not 10 <= len(password) <= 128:
        raise ValueError("密码长度必须为 10～128 个字符")
    if db.scalar(select(AppUser.id).where(AppUser.login == login)):
        raise ValueError("账号已存在，不覆盖原账号")
    user = AppUser(login=login, password_hash=hash_password(password), role=role)
    db.add(user)
    db.commit()
    return user


def main():
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", encoding="utf-8-sig")
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate")
    user_parser = commands.add_parser("create-user")
    user_parser.add_argument("--login", required=True)
    user_parser.add_argument("--role", choices=list(Role), default=Role.BUSINESS)
    args = parser.parse_args()
    try:
        if args.command == "migrate":
            upgrade_database(get_engine())
            print("业务数据库已迁移到最新版本。")
        else:
            password = getpass("输入新账号密码（10～128 字符，不回显）：")
            if password != getpass("再次输入密码："):
                raise ValueError("两次密码不一致")
            with Session(get_engine()) as db:
                create_user(db, args.login, password, Role(args.role))
            print("本地账号已创建。")
    except (ValidationError, ValueError):
        raise SystemExit("参数无效或账号已存在，请检查输入。") from None
    except IntegrityError:
        raise SystemExit("账号或数据库约束冲突，未覆盖现有数据。") from None
    except SQLAlchemyError:
        raise SystemExit("数据库操作失败，请检查服务、连接配置和迁移版本。") from None


if __name__ == "__main__":
    main()
