import json
import pytest
from alfred.slack.block_builder import BlockBuilder

@pytest.fixture
def sample_todos():
    return [
        {
            "todo_id": 101,
            "user_id": "U12345",
            "todo_content": "Fix critical bug in production",
            "status": "pending",
            "remind_time": "10:00",
            "due_time": "2023-10-27 12:00",
            "ddl_time": "2023-10-27 12:00"
        },
        {
            "todo_id": 102,
            "user_id": "U67890",
            "todo_content": "Update API documentation",
            "status": "completed",
            "remind_time": "14:00",
            "due_time": "2023-10-28 18:00",
            "ddl_time": "2023-10-28 18:00"
        }
    ]

@pytest.mark.parametrize("style", ["standard", "saas", "gitflow"])
def test_block_builder_styles_output(sample_todos, style, capsys):
    """
    Test that BlockBuilder generates blocks for each style.
    Prints the JSON output for manual inspection in Slack Block Kit Builder.
    """
    BlockBuilder.set_style(style)
    
    # Test Notify Blocks
    normal_todos = [sample_todos[0]]
    overdue_todos = [sample_todos[1]] # Treating one as overdue for variety
    
    blocks = BlockBuilder.build_notify_blocks(normal_todos, overdue_todos)
    
    assert isinstance(blocks, list)
    assert len(blocks) > 0
    
    print(f"\n\n=== STYLE: {style.upper()} ===")
    print("--- Notify Blocks (Copy below to Slack Block Kit Builder) ---")
    print(json.dumps(blocks, indent=2, ensure_ascii=False))
    
    # Test Single Todo Block
    single_block = BlockBuilder.build_single_todo_blocks(sample_todos[0])
    assert isinstance(single_block, list)
    assert len(single_block) > 0
    
    print("\n--- Single Todo Block ---")
    print(json.dumps(single_block, indent=2, ensure_ascii=False))
    print("==========================================================\n")

    # We use capsys to ensure output is captured if needed, 
    # but for "printing" to see it during test run with -s, simple print works.

if __name__ == "__main__":
    import pytest
    pytest.main(['-s', __file__])
