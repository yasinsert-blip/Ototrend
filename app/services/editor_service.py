from app.database.crud import (
    get_editor_news,
    get_news_by_status,
    filter_news,
    search_news,
    get_brands,
    get_categories,
)


def get_editor_dashboard():

    return get_editor_news()



def get_editor_by_status(status):

    return get_news_by_status(status)



def get_filtered_news(
    status=None,
    brand=None,
    category=None,
):

    return filter_news(
        status=status,
        brand=brand,
        category=category,
    )



def search_editor_news(keyword):

    return search_news(keyword)



def get_brand_list():

    return get_brands()



def get_category_list():

    return get_categories()



# ==========================================================
# EDITOR DASHBOARD STATS
# ==========================================================

def get_dashboard_stats():

    all_news = get_editor_news()

    stats = {

        "total_news": len(all_news),

        "ai_pending": 0,

        "ai_ready": 0,

        "editor_review": 0,

        "instagram_ready": 0,

        "scheduled": 0,

        "published": 0,

    }


    for news in all_news:
        print(
            "STATUS:",
            news.status
        )

        if news.status == "new":

            stats["ai_pending"] += 1


        elif news.status == "ai_ready":

            stats["ai_ready"] += 1


        elif news.status == "editor_review":

            stats["editor_review"] += 1


        elif news.status == "instagram_ready":

            stats["instagram_ready"] += 1


        elif news.status == "scheduled":

            stats["scheduled"] += 1


        elif news.status == "published":

            stats["published"] += 1



    return stats