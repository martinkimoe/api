from sqlalchemy.dialects.mysql import INTEGER, BIGINT
from zeeguu.core.model import db

class YTChannel(db.Model):
    __tablename__ = 'yt_channel'
    __table_args__ = {"mysql_collate": "utf8_bin"}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    channel_id = db.Column(db.String(512), unique=True, nullable=False)
    name = db.Column(db.String(512))
    description = db.Column(db.Text)
    views = db.Column(BIGINT(unsigned=True))
    subscribers = db.Column(INTEGER(unsigned=True))
    language_id = db.Column(db.Integer, db.ForeignKey("language.id"))
    should_crawl = db.Column(db.Integer)
    last_crawled = db.Column(db.DateTime)

    videos = db.relationship("Video", back_populates="channel")
    language = db.relationship("Language")

    def __init__(self, channel_id, name, description, views, subscribers, language, should_crawl, last_crawled):
        self.channel_id = channel_id
        self.name = name
        self.description = description
        self.views = views
        self.subscribers = subscribers
        self.language = language
        self.should_crawl = should_crawl
        self.last_crawled = last_crawled

    def __repr__(self):
        return f'<YTChannel {self.name} ({self.channel_id})>'

    def as_dictionary(self):
        return dict(
            id=self.id,
            channel_id=self.channel_id,
            name=self.name,
            description=self.description,
            views=self.views,
            subscribers=self.subscribers,
            language_id=self.language.id,
            should_crawl=self.should_crawl,
            last_crawled=self.last_crawled
        )

    @classmethod
    def find_or_create(
        cls, 
        session, 
        channel_id, 
        name=None, 
        description=None,
        views=None,
        subscribers=None,
        language=None,
        should_crawl=None,
        last_crawled=None
    ):
        channel = session.query(cls).filter_by(channel_id=channel_id).first()

        if channel:
            return channel

        new_channel = cls(
            channel_id = channel_id,
            name = name,
            description = description,
            views = views,
            subscribers = subscribers,
            language = language,
            should_crawl = should_crawl,
            last_crawled = last_crawled
        )
        session.add(new_channel)

        try:
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        
        return new_channel