from agents.leave_assistant.knowledge_local import search


def test_policy_search_grounds_and_cites():
    out = search("年假什么时候过期")
    assert out["grounded"] is True
    titles = " ".join(r["section"] for r in out["results"])
    assert "年假" in titles or "有效期" in titles
    assert all(r["source"] == "hr-leave-policies" for r in out["results"])


def test_policy_search_sick_leave_proof():
    out = search("病假需要什么材料")
    assert out["grounded"] is True
    assert any("病假" in r["section"] for r in out["results"])


def test_policy_search_no_answer_is_not_fabricated():
    out = search("公司允许养宠物假吗")
    assert out["grounded"] is False
    assert out["results"] == []
