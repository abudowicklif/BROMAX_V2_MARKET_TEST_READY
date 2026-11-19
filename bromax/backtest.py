from collections import Counter
import numpy as np
import pandas as pd

def evaluate_digits(digits):
    arr=np.asarray(digits,dtype=int)
    n=len(arr)
    if n==0:
        return {"n":0,"hit_rate":None,"baseline":0.1,"ci95":None}
    hits=int(np.sum(arr==arr)) # placeholder replaced by evaluate_predictions
    return {"n":n,"baseline":0.1}

def evaluate_predictions(predicted, actual, probabilities=None):
    pred=np.asarray(predicted,dtype=int); actual=np.asarray(actual,dtype=int)
    if len(pred)!=len(actual) or len(actual)==0:
        raise ValueError("Predicted and actual arrays must have same non-zero length")
    hit=(pred==actual)
    n=len(actual); rate=float(hit.mean())
    se=(rate*(1-rate)/n)**0.5
    result={"n":n,"hits":int(hit.sum()),"hit_rate":rate,"baseline":0.10,
            "approx_ci95":[max(0,rate-1.96*se),min(1,rate+1.96*se)],
            "baseline_excess":rate-0.10}
    if probabilities is not None:
        p=np.asarray(probabilities,dtype=float)
        if p.shape!=(n,10): raise ValueError("probabilities must have shape (n,10)")
        p=np.clip(p,1e-12,1); p=p/p.sum(axis=1,keepdims=True)
        onehot=np.eye(10)[actual]
        result["log_loss"]=float(-np.log(p[np.arange(n),actual]).mean())
        result["brier_score"]=float(((p-onehot)**2).sum(axis=1).mean())
    return result

def walk_forward(digits, train_size=1000, test_size=250):
    """Leakage-safe naive baseline benchmark; forecasts use only prior training context.
    It intentionally does not claim a predictive edge. Returns chronological fold metrics.
    """
    values=np.asarray(digits,dtype=int)
    folds=[]
    start=train_size
    while start < len(values):
        end=min(start+test_size,len(values))
        train=values[:start]
        # Baseline forecast is the smoothed most-frequent digit in the past only.
        counts=np.bincount(train,minlength=10)+1
        candidate=int(np.argmax(counts))
        pred=np.full(end-start,candidate)
        folds.append({"train_end_index":start,"test_start_index":start,
                      "test_end_index":end,**evaluate_predictions(pred,values[start:end])})
        start=end
    return {"folds":folds,"total_test_ticks":sum(f["n"] for f in folds),
            "method":"chronological expanding-window frequency baseline",
            "warning":"Baseline benchmark only; model selection requires separate train/validation/test periods."}
