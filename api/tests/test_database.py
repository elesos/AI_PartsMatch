from sqlalchemy import create_engine, inspect

from app.models import Base


def test_all_foundation_tables_can_be_created_and_queried() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    expected = {
        "part", "part_image", "machine", "machine_part_relation", "part_cross_reference",
        "part_alias", "cart_item", "manual_ticket", "part_query_log", "ai_match_evidence",
        "sys_configs", "file_object", "admin_user",
        "excel_batch", "excel_batch_row", "excel_batch_job",
    }
    assert expected <= set(inspect(engine).get_table_names())
