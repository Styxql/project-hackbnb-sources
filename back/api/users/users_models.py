from typing import List
import hmac
from hashlib import md5
from werkzeug.security import generate_password_hash, check_password_hash
from database.init import db
from sqlalchemy.orm import Mapped, mapped_column, relationship

class User(db.Model):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    email: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str] = mapped_column()
    rooms: Mapped[List["Room"]] = relationship(back_populates="host_user")

    def __repr__(self):
        return f'<User {self.email!r}>'

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
        }

    def to_public_dict(self):
        # version publique utilisée pour l'hôte d'un logement, sans l'email
        return {
            "id": self.id,
            "name": self.name,
        }

    def set_password(self, clear_password: str):
        # Fix : MD5 sans sel se casse très vite, on passe sur scrypt (fourni par werkzeug)
        self.password_hash = generate_password_hash(clear_password)

    def is_valid_password(self, clear_password: str) -> bool:
        if not self.password_hash:
            return False

        # anciens comptes encore en MD5 (32 car. hexa) : si le mdp est bon on re-hash en scrypt
        if len(self.password_hash) == 32 and "$" not in self.password_hash:
            legacy_hash = md5(clear_password.encode("utf-8")).hexdigest()
            if hmac.compare_digest(legacy_hash, self.password_hash):
                self.set_password(clear_password)
                return True
            return False

        try:
            return check_password_hash(self.password_hash, clear_password)
        except ValueError:
            return False
