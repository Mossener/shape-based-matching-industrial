"""V31 timing fixtures are generated numeric rows, never actual timings."""
import copy
import csv
import io
import unittest
import timing_audit as audit


def fixture(objects=(1,2),frames=((1,0),(4,20))):
    references={(obj,scene,image,arm):(10+obj,2+obj)
        for obj in objects for scene,image in frames for arm in
        ('rgb_control','rgb_pooled_features','rgb_stratified_features')}
    arms=('rgb_control','rgb_pooled_features','rgb_stratified_features')
    variants=tuple((arm,path) for arm in arms for path in ('fallback','fused'))
    rows=[]
    for obj in objects:
        for ordinal,(scene,image) in enumerate(frames):
            for round_id in range(13):
                for order in range(6):
                    arm,path=variants[(order+ordinal+round_id)%6]
                    base=10000 if round_id==0 else obj*10+round_id
                    value=base*(1,.5,.25)[arms.index(arm)]
                    raw,selected=references[(obj,scene,image,arm)]
                    rows.append(dict(object_id=str(obj),scene=str(scene),image=str(image),
                        frame_ordinal=str(ordinal),round=str(round_id),warmup=str(int(round_id==0)),
                        order=str(order),arm=arm,path=path,match_ms=str(value),
                        external_call_ms=str(value+2),raw=str(raw),selected=str(selected),exact_own_reference='1'))
    pairs=[]
    for obj in objects:
        for ordinal,(scene,image) in enumerate(frames):
            for round_id in range(1,13):
                samples={(r['arm'],r['path']):r for r in rows if int(r['object_id'])==obj and
                    int(r['frame_ordinal'])==ordinal and int(r['round'])==round_id}
                for path in ('fallback','fused'):
                    for numerator,denominator in [(arms[1],arms[0]),(arms[2],arms[0]),(arms[2],arms[1])]:
                        n,d=samples[(numerator,path)],samples[(denominator,path)]
                        pairs.append(dict(object_id=str(obj),scene=str(scene),image=str(image),frame_ordinal=str(ordinal),
                            round=str(round_id),path=path,numerator=numerator,denominator=denominator,
                            match_ratio=str(float(n['match_ms'])/float(d['match_ms'])),
                            external_ratio=str(float(n['external_call_ms'])/float(d['external_call_ms']))))
    return list(frames),objects,references,rows,pairs


class TimingTests(unittest.TestCase):
    def setUp(self):self.frames,self.objects,self.references,self.rows,self.pairs=fixture()

    def grouped(self,rows=None):
        try:return audit.validate_timing_rows(self.rows if rows is None else rows,self.frames,
            self.references,expected_calls=312,objects=self.objects)
        except audit.AuditError as error:self.fail('Valid V31 six-variant schedule rejected: '+str(error))

    def test_exact_v31_constants_and_header(self):
        self.assertEqual(len(audit.VARIANTS),6,'V31 must use six variants')
        self.assertEqual(audit.EXPECTED_CALLS,29952)
        self.assertEqual(audit.FORMAL_ROUNDS,tuple(range(1,13)))
        self.assertIn('frame_ordinal',audit.TIMING_HEADER)

    def test_valid_balanced_route_and_warmup_exclusion(self):
        grouped=self.grouped();variants,paired=audit.recompute_statistics(grouped['formal'])
        self.assertEqual([v['samples'] for v in variants],[48]*6)
        self.assertTrue(all(v['match_p95_ms']<100 for v in variants))
        self.assertEqual(len(paired),6)
        self.assertEqual(paired[0]['match_ratio_median'],.5)
        self.assertTrue(all(all(n==2 for n in positions.values()) for positions in grouped['order_balance'].values()))

    def test_route_identity_flags_counts_and_clocks_mutations(self):
        for field,value in [('frame_ordinal','1'),('order','1'),('arm','rgb_pooled_features'),('warmup','0'),
            ('round','12'),('raw','999'),('selected','999'),('exact_own_reference','0'),
            ('match_ms','nan'),('external_call_ms','0')]:
            rows=copy.deepcopy(self.rows);rows[0][field]=value
            with self.subTest(field=field),self.assertRaises(audit.AuditError):
                audit.validate_timing_rows(rows,self.frames,self.references,312,self.objects)
        for rows in [self.rows[:-1],self.rows+self.rows[:1],self.rows[:6]+self.rows[12:]+self.rows[6:12]]:
            with self.assertRaises(audit.AuditError):audit.validate_timing_rows(rows,self.frames,self.references,312,self.objects)

    def test_pair_csv_is_bound_to_same_frame_round_path_and_direction(self):
        grouped=self.grouped();method=getattr(audit,'validate_pair_rows',None)
        self.assertTrue(callable(method),'Full V31 pair CSV verifier is missing')
        result=method(self.pairs,grouped['by_frame'],self.frames,self.objects)
        self.assertEqual(result['rows'],288)
        for key,value in [('numerator','rgb_control'),('denominator','rgb_stratified_features'),
            ('frame_ordinal','1'),('round','0'),('match_ratio','9'),('external_ratio','nan')]:
            rows=copy.deepcopy(self.pairs);rows[0][key]=value
            with self.subTest(key=key),self.assertRaises(audit.AuditError):method(rows,grouped['by_frame'],self.frames,self.objects)
        for rows in [self.pairs[:-1],self.pairs+self.pairs[:1]]:
            with self.assertRaises(audit.AuditError):method(rows,grouped['by_frame'],self.frames,self.objects)

    def test_same_round_ratios_do_not_become_ratio_of_medians(self):
        method=getattr(audit,'COMPARISONS',None)
        self.assertTrue(method,'Explicit P/C0 B/C0 B/P comparisons are missing')
        groups={}
        for arm,path in audit.VARIANTS:
            values=[1,10,100] if arm=='rgb_control' else [2,100,300]
            groups[(arm,path)]=[dict(object_id=1,scene=1,image=1,round=i+1,match_ms=v,external_call_ms=v+1) for i,v in enumerate(values)]
        _,paired=audit.recompute_statistics(groups)
        p=next(p for p in paired if p['numerator']=='rgb_pooled_features' and p['denominator']=='rgb_control')
        self.assertEqual(p['match_ratio_median'],3)
        self.assertNotEqual(p['match_ratio_median'],10)
        self.assertEqual(audit.nearest_rank([100,1,10,20],.5),10)

    def test_equal_frame_then_equal_object_and_tail_regressions(self):
        result=audit.additional_equal_frame_summary(self.grouped()['by_frame'],self.objects,2)
        self.assertEqual(len(result['frame_medians']),4)
        self.assertEqual(result['equal_object_overall']['variants']['rgb_control/fallback']['mean_frame_match_median_ms'],21)
        self.assertEqual(len(result['frame_regressions']),6)
        self.assertTrue(all(x['frames_match_ratio_gt1']==0 for x in result['frame_regressions']))

    def test_summary_has_six_variants_without_inherited_two_arm_pair_array(self):
        variants,_=audit.recompute_statistics(self.grouped()['formal'])
        summary=dict(passed=1,stage='timing',objects=list(audit.OBJECTS),unique_frames=64,
            object_frame_combinations=384,matcher_calls=29952,warmup_rounds=1,measured_rounds=12,
            formal_rows=27648,exact_own_reference_every_call=1,decode_total_ms=10,peak_rss_bytes=1024,
            decode_and_bank_load_excluded_from_external_call=1,paired_performance_benchmark=1,variants=variants)
        try:audit.validate_stage_summary(summary,variants)
        except TypeError:self.fail('V31 summary still requires V30 native paired array')
        for key,value in [('measured_rounds',7),('matcher_calls',12288),('formal_rows',1)]:
            bad=copy.deepcopy(summary);bad[key]=value
            with self.assertRaises(audit.AuditError):audit.validate_stage_summary(bad,variants)
        bad=copy.deepcopy(summary);bad['variants'][0]['match_p95_ms']+=1
        with self.assertRaises(audit.AuditError):audit.validate_stage_summary(bad,variants)


if __name__=='__main__':unittest.main()
