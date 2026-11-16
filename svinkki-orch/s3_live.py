import sys
sys.path.insert(0, "C:/Users/onnik/Desktop/svinkki-s3/.devloop/live-check")
import harness
harness.AGENT = "agent-s3"
harness.PLANS["cache"] = [("claude-opus-5-5", [["How much did I spend on taxis last month?", "and the month before?"]])]
sys.argv = ["harness", "--plan", "cache", "--budget", "2", "--port", "8030", "--out", "C:/Users/onnik/Desktop/svinkki-orch/live-check-s3"]
harness.main()
