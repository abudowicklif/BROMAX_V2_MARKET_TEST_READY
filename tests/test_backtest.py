import pytest
from bromax.backtest import evaluate_predictions, walk_forward

def test_metrics():
    r=evaluate_predictions([1,2,3],[1,0,3])
    assert r["n"]==3 and r["hits"]==2
    assert 0 <= r["hit_rate"] <= 1

def test_probability_metrics():
    p=[[.1]*10,[.1]*10]
    r=evaluate_predictions([0,0],[0,1],p)
    assert "log_loss" in r and "brier_score" in r

def test_walk_forward_chronological():
    r=walk_forward([i%10 for i in range(1300)],1000,150)
    assert r["total_test_ticks"]==300
    assert r["folds"][0]["test_start_index"]==1000
