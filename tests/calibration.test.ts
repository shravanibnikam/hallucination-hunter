import { expect,test } from "vitest";
import { calibration } from "@/lib/calibration";
import { shareScore } from "@/lib/share";
const guess=(confidence:number,is_correct:boolean,is_attention_check=false)=>({confidence,is_correct,is_attention_check});
test("confidence mapping",()=>{[50,62.5,75,87.5,100].forEach((p,i)=>expect(calibration([guess(i+1,true)]).statedProbability).toBe(p));});
test("calibration labels and attention exclusions",()=>{expect(calibration([guess(5,false)]).message).toContain("overconfident");expect(calibration([guess(1,true)]).message).toContain("underconfident");expect(calibration([guess(5,true),guess(1,false,true)]).message).toContain("well calibrated");expect(calibration([]).actualAccuracy).toBeNull();});
test("threshold is strictly greater than ten points",()=>{const g=Array.from({length:10},(_,i)=>guess(5,i!==0));expect(calibration(g).message).toContain("well calibrated");g[1].is_correct=false;expect(calibration(g).message).toContain("overconfident");});
test("share params accept only bounded scores",()=>{expect(shareScore({score:"8",total:"10"})).toEqual({score:8,total:10});for(const value of [{},{score:11,total:10},{score:-1,total:10},{score:1,total:0},{score:"hello",total:10},{score:1.5,total:10}])expect(shareScore(value)).toBeNull();});
