import scrapy
from scrapy.exceptions import DropItem

from pipelines.scrapy_pipeline import ValidationPipeline
from scraper.items import ReviewItem
from scraper.spiders.airlinequality import AirlineQualitySpider


def test_airlinequality_start_requests_only_yields_requests() -> None:
    spider = AirlineQualitySpider(airline="british-airways", max_pages="1")

    assert all(isinstance(item, scrapy.Request) for item in spider.start_requests())


def test_review_parser_requires_complete_quality_fields() -> None:
    spider = AirlineQualitySpider(airline="british-airways", max_pages="1")
    html = """
    <article itemprop="review">
      <h2 class="text_header">"Great cabin crew"</h2>
      <time datetime="2026-05-19"></time>
      <span itemprop="ratingValue">9</span>
      <div itemprop="reviewBody">Trip Verified | Excellent cabin crew and efficient boarding experience.</div>
      <table><tr><td>Recommended</td><td>yes</td></tr></table>
    </article>
    """

    item = spider._parse_card(
        html, {"slug": "british-airways", "name": "British Airways"}, "https://example.test"
    )

    assert item is not None
    assert item["title"] == "Great cabin crew"
    assert item["rating"] == 9.0
    assert item["review_date"] == "2026-05-19"


def test_validation_pipeline_drops_incomplete_reviews() -> None:
    pipeline = ValidationPipeline()
    item = ReviewItem(text="short", title="", rating=None, review_date=None, fingerprint="abc")

    try:
        pipeline.process_item(item, spider=None)
    except DropItem as exc:
        assert "missing required fields" in str(exc)
    else:
        raise AssertionError("Expected DropItem")
