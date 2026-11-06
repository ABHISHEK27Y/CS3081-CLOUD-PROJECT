import clean


def rec(rid, text, raw):
    return {"id": rid, "text": text, "teacher_raw": raw}


def test_counts_partition_and_each_reason():
    recs = [
        rec("C1", "set an alarm for seven am",
            '{"intent":"alarm_set","date":null,"time":"seven am","place":null}'),   # keep
        rec("C2", "bad json", "not json"),                                           # (a)
        rec("C3", "weather in london",
            '{"intent":"weather_query","date":null,"place":"london"}'),             # (b) only 3 keys
        rec("C4", "hello there",
            '{"intent":"nope","date":null,"time":null,"place":null}'),              # (c) bad intent
        rec("C5", "what time is it",
            '{"intent":"datetime_query","date":null,"time":null,"place":"paris"}'),  # (d) paris not in text
        rec("C6", "set an alarm for seven am",
            '{"intent":"alarm_set","date":null,"time":"seven am","place":null}'),   # duplicate of C1
    ]
    rows, counts = clean.clean_records(recs)
    assert counts["input"] == 6
    assert counts["a"] == 1
    assert counts["b"] == 1
    assert counts["c"] == 1
    assert counts["d"] == 1
    assert counts["duplicates"] == 1
    assert counts["kept"] == 1
    # the key invariant the handout asks the report to show
    assert (counts["a"] + counts["b"] + counts["c"] + counts["d"]
            + counts["duplicates"] + counts["kept"]) == counts["input"]
    assert [r["id"] for r in rows] == ["C1"]


def test_duplicate_keeps_smallest_id_and_id_order():
    recs = [
        rec("C9", "turn on the light",
            '{"intent":"calendar_set","date":null,"time":null,"place":null}'),
        rec("C2", "turn on the light",
            '{"intent":"calendar_set","date":null,"time":null,"place":null}'),
        rec("C5", "what is the weather in paris",
            '{"intent":"weather_query","date":null,"time":null,"place":"paris"}'),
    ]
    rows, counts = clean.clean_records(recs)
    assert counts["duplicates"] == 1
    assert [r["id"] for r in rows] == ["C2", "C5"]  # smallest id kept, output in id order


def test_slot_must_be_substring_of_command():
    assert clean.classify(rec("X", "alarm for seven am",
        '{"intent":"alarm_set","date":null,"time":"seven am","place":null}'))[0] == "keep"
    # value not present in the command -> reason d
    assert clean.classify(rec("X", "alarm for seven am",
        '{"intent":"alarm_set","date":null,"time":"eight pm","place":null}')) == "d"
