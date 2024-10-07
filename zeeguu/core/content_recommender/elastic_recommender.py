"""

 Recommender that uses ElasticSearch instead of mysql for searching.
 Based on mixed recommender.
 Still uses MySQL to find relations between the user and things such as:
   - topics, language and user subscriptions.

"""

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, Q, SF
from pprint import pprint

from zeeguu.core.model import (
    Article,
    TopicFilter,
    TopicSubscription,
    NewTopicFilter,
    NewTopicSubscription,
    SearchFilter,
    SearchSubscription,
    UserArticle,
    Language,
)

from zeeguu.core.elastic.elastic_query_builder import (
    build_elastic_recommender_query,
    build_elastic_search_query,
    build_elastic_more_like_this_query,
)
from zeeguu.core.util.timer_logging_decorator import time_this
from zeeguu.core.elastic.settings import ES_CONN_STRING, ES_ZINDEX


def filter_hits_on_score(hits, score_threshold):
    return [h for h in hits if h["_score"] > score_threshold]


def _prepare_user_constraints(user):
    language = user.learned_language

    # 0. Ensure appropriate difficulty
    declared_level_min, declared_level_max = user.levels_for(language)
    lower_bounds = declared_level_min * 10
    upper_bounds = declared_level_max * 10

    # 1. Unwanted user topics
    # ==============================
    user_search_filters = SearchFilter.all_for_user(user)
    unwanted_user_topics = []
    for user_search_filter in user_search_filters:
        unwanted_user_topics.append(user_search_filter.search.keywords)
    print(f"keywords to exclude: {unwanted_user_topics}")

    # 2. Topics to exclude / filter out
    # =================================
    excluded_topics = TopicFilter.all_for_user(user)
    topics_to_exclude = [
        each.topic.title for each in excluded_topics if each is not None
    ]
    print(f"topics to exclude: {topics_to_exclude}")

    # 3. Topics subscribed, and thus to include
    # =========================================
    topic_subscriptions = TopicSubscription.all_for_user(user)
    topics_to_include = [
        subscription.topic.title
        for subscription in topic_subscriptions
        if subscription is not None
    ]
    print(f"topics to include: {topic_subscriptions}")

    # 4. New Topics to exclude / filter out
    # =================================
    excluded_new_topics = NewTopicFilter.all_for_user(user)
    new_topics_to_exclude = [
        each.new_topic.title for each in excluded_new_topics if each is not None
    ]
    print(f"New Topics to exclude: {topics_to_exclude}")

    # 5. New Topics subscribed, and thus to include
    # =========================================
    topic_new_subscriptions = NewTopicSubscription.all_for_user(user)
    new_topics_to_include = [
        subscription.new_topic.title
        for subscription in topic_new_subscriptions
        if subscription is not None
    ]
    print(f"New Topics to include: {topic_subscriptions}")

    # 6. Wanted user topics
    # =========================================
    user_subscriptions = SearchSubscription.all_for_user(user)

    wanted_user_topics = []
    for sub in user_subscriptions:
        wanted_user_topics.append(sub.search.keywords)
    print(f"keywords to include: {wanted_user_topics}")

    return (
        language,
        upper_bounds,
        lower_bounds,
        _list_to_string(topics_to_include),
        _list_to_string(topics_to_exclude),
        _new_topics_to_string(new_topics_to_include),
        _new_topics_to_string(new_topics_to_exclude),
        _list_to_string(wanted_user_topics),
        _list_to_string(unwanted_user_topics),
    )


def article_recommendations_for_user(
    user,
    count,
    page=0,
    es_scale="1d",
    es_offset="1d",
    es_decay=0.6,
    es_weight=4.2,
    score_threshold_for_search=5,
    maximum_added_search_articles=10,
):
    """
        Retrieve up to :param count + maximum_added_search_articles articles
        which are equally distributed over all the feeds to which the :param user
        is registered to.

        The articles are prioritized based on recency and the difficulty, preferring
        articles that are close to the users level.

        The search articles prioritize finding the searches the user has saved, so that
        these articles are still shown even if not tagged by the topics selected.

        Fails if no language is selected.

    :return:

    """

    final_article_mix = []
    (
        language,
        upper_bounds,
        lower_bounds,
        topics_to_include,
        topics_to_exclude,
        new_topics_to_include,
        new_topics_to_exclude,
        wanted_user_topics,
        unwanted_user_topics,
    ) = _prepare_user_constraints(user)
    # build the query using elastic_query_builder
    query_body = build_elastic_recommender_query(
        count,
        topics_to_include,
        topics_to_exclude,
        wanted_user_searches,
        unwanted_user_searches,
        language,
        upper_bounds,
        lower_bounds,
        es_scale,
        es_offset,
        es_decay,
        es_weight,
        new_topics_to_include=new_topics_to_include,
        new_topics_to_exclude=new_topics_to_exclude,
        page=page,
    )

    es = Elasticsearch(ES_CONN_STRING)
    res = es.search(index=ES_ZINDEX, body=query_body)

    hit_list = res["hits"].get("hits")
    final_article_mix.extend(_to_articles_from_ES_hits(hit_list))

    # Get articles based on Search preferences
    articles_from_searches = []
    for search in wanted_user_searches.split():
        articles_from_searches += article_search_for_user(
            user,
            1,
            search,
            page,
            score_threshold=score_threshold_for_search,
            use_published_priority=True,
            use_readability_priority=True,
        )

    # Limit the searched added articles to a maximum of 10 extra articles.
    articles = [
        a for a in final_article_mix if a is not None and not a.broken
    ] + articles_from_searches[:maximum_added_search_articles]

    sorted_articles = sorted(articles, key=lambda x: x.published_time, reverse=True)

    return sorted_articles


@time_this
def article_search_for_user(
    user,
    count,
    search_terms,
    page=0,
    es_time_scale="1d",
    es_time_offset="1d",
    es_time_decay=0.65,
    use_published_priority=False,
    use_readability_priority=True,
    score_threshold=0,
):
    final_article_mix = []

    (
        language,
        upper_bounds,
        lower_bounds,
        topics_to_include,
        topics_to_exclude,
        new_topics_to_include,
        new_topics_to_exclude,
        wanted_user_topics,
        unwanted_user_topics,
    ) = _prepare_user_constraints(user)

    # build the query using elastic_query_builder
    query_body = build_elastic_search_query(
        count,
        search_terms,
        topics_to_include,
        topics_to_exclude,
        wanted_user_topics,
        unwanted_user_topics,
        language,
        upper_bounds,
        lower_bounds,
        es_time_scale,
        es_time_offset,
        es_time_decay,
        page,
        use_published_priority,
        use_readability_priority,
    )

    es = Elasticsearch(ES_CONN_STRING)
    res = es.search(index=ES_ZINDEX, body=query_body)
    hit_list = res["hits"].get("hits")
    if score_threshold > 0:
        hit_list = filter_hits_on_score(hit_list, score_threshold)
    final_article_mix.extend(_to_articles_from_ES_hits(hit_list))
    final_articles = [a for a in final_article_mix if a is not None and not a.broken]

    return final_articles


def topic_filter_for_user(
    user,
    count,
    newer_than,
    media_type,
    max_duration,
    min_duration,
    difficulty_level,
    topic,
):
    es = Elasticsearch(ES_CONN_STRING)

    s = Search().query(Q("term", language=user.learned_language.code()))

    if newer_than:
        s = s.filter("range", published_time={"gte": f"now-{newer_than}d/d"})

    AVERAGE_WORDS_PER_MINUTE = 70

    if max_duration:
        s = s.filter(
            "range", word_count={"lte": int(max_duration) * AVERAGE_WORDS_PER_MINUTE}
        )

    if min_duration:
        s = s.filter(
            "range", word_count={"gte": int(min_duration) * AVERAGE_WORDS_PER_MINUTE}
        )

    if media_type:
        if media_type == "video":
            s = s.filter("term", video=1)
        else:
            s = s.filter("term", video=0)

    if topic != None and topic != "all":
        s = s.filter("match", topics=topic.lower())

    if difficulty_level:
        lower_bounds, upper_bounds = _difficuty_level_bounds()
        s = s.filter("range", fk_difficulty={"gte": lower_bounds, "lte": upper_bounds})

    query = s.query

    query_with_size = {
        "size": count,
        "query": query.to_dict(),
        "sort": [{"published_time": "desc"}],
    }

    res = es.search(index=ES_ZINDEX, body=query_with_size)

    hit_list = res["hits"].get("hits")

    final_article_mix = _to_articles_from_ES_hits(hit_list)

    return [a for a in final_article_mix if a is not None and not a.broken]


def _list_to_string(input_list):
    return " ".join([each for each in input_list]) or ""


def _new_topics_to_string(input_list):
    return ",".join(input_list)


def _to_articles_from_ES_hits(hits):
    articles = []
    for hit in hits:
        articles.append(Article.find_by_id(hit.get("_id")))
    return articles


def _difficuty_level_bounds(level):
    lower_bounds = 1
    upper_bounds = 10

    if level == "easy":
        upper_bounds = 5
    elif level == "challenging":
        lower_bounds = 5
    else:
        lower_bounds = 4
        upper_bounds = 8
    return lower_bounds, upper_bounds


def __find_articles_like(
    recommended_articles_ids: "list[int]",
    limit: int,
    article_age: int,
    language_id: int,
) -> "list[Article]":
    es = Elasticsearch(ES_CONN_STRING)
    fields = ["content", "title"]
    language = Language.find_by_id(language_id)
    like_documents = [
        {"_index": ES_ZINDEX, "_id": str(doc_id)} for doc_id in recommended_articles_ids
    ]

    mlt_query = build_elastic_more_like_this_query(
        language=language,
        like_documents=like_documents,
        similar_to=fields,
        cutoff_days=article_age,
    )

    res = es.search(index=ES_ZINDEX, body=mlt_query, size=limit)
    articles = _to_articles_from_ES_hits(res["hits"]["hits"])
    articles = [a for a in articles if a.broken == 0]
    return articles


def content_recommendations(user_id: int, language_id: int):
    query = UserArticle.all_liked_articles_of_user_by_id(user_id)

    user_likes = []
    for article in query:
        if article.article.language_id == language_id:
            user_likes.append(article.article_id)

    articles_to_recommend = __find_articles_like(user_likes, 20, 50, language_id)
    return articles_to_recommend
