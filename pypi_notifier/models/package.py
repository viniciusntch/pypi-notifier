import logging
import xmlrpc.client
from datetime import datetime, timedelta
from sqlalchemy import or_
from sqlalchemy.ext.associationproxy import association_proxy
from pypi_notifier.extensions import db, cache
from pypi_notifier.models.util import commit_or_rollback


logger = logging.getLogger(__name__)


class Package(db.Model):
    __tablename__ = 'packages'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True)
    latest_version = db.Column(db.String(20))
    updated_at = db.Column(db.DateTime)
    last_check = db.Column(db.DateTime)

    repos = association_proxy('requirements', 'repo')

    pypi = xmlrpc.client.ServerProxy('https://pypi.python.org/pypi')

    def __init__(self, name):
        self.name = name.lower()

    def __repr__(self):
        return "<Package %s>" % self.name

    @property
    def url(self):
        return "https://pypi.python.org/pypi/%s" % self.original_name

    @classmethod
    def update_all_packages(cls):
        packages = cls.query.filter(
            or_(
                cls.last_check <= datetime.utcnow() - timedelta(days=1),
                cls.last_check.is_(None),
            )
        ).all()
        for package in packages:
            with commit_or_rollback():
                package.update_from_pypi()

    @classmethod
    @cache.cached(timeout=3600, key_prefix='all_packages')
    def get_all_names(cls):
        packages = cls.pypi.list_packages()
        return {name.lower(): name for name in packages if name}

    @property
    def original_name(self):
        return self.get_all_names()[self.name.lower()]

    def find_latest_version(self):
        version = self.pypi.package_releases(self.original_name)[0]
        logger.info("Latest version of %s is %s", self.original_name, version)
        return version

    def update_from_pypi(self):
        """
        Updates the latest version of the package by asking PyPI.

        """
        latest = self.find_latest_version()
        self.last_check = datetime.utcnow()
        if self.latest_version != latest:
            self.latest_version = latest
            self.updated_at = datetime.utcnow()
