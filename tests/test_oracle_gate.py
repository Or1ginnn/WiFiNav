import unittest
from connectivity_vln.evaluation.oracle import assess


POLICY = {'maximum_paired_absolute_spl_loss':.02,'maximum_paired_absolute_ndtw_loss':.03,
          'maximum_paired_total_path_increase':.2,'minimum_paired_total_outage_reduction':.1,
          'maximum_paired_total_longest_outage_increase':0.}


def row(w, *, ok=1., outage=20., ratio=.5):
    return {'episode_id':'a','layout_id':'near','lambda':w,'run_dir':str(w),
            'status':{'return_code':0,'timed_out':False,'wall_seconds':1.},
            'summary':{'error':None,'model_request_attempts':1,'metrics':{
                'success':ok,'spl':.7 if ok else 0.,'ndtw_exact_euclidean':.8,'path_length_m':10.}},
            'communication':{'outage_seconds':outage,'outage_ratio':ratio,
                             'longest_outage_seconds':5.,'weak_seconds':25.,'motion_time_seconds':40.}}


class OracleGateTest(unittest.TestCase):
    def evaluate(self, rows):
        return assess(rows,{'lambda_values':[0.,1.],'acceptance':POLICY},{('a','near')})

    def test_successful_absolute_exposure_improvement(self):
        result=self.evaluate([row(0.),row(1.,outage=15.)])
        self.assertEqual(result['selected_lambda'],1.)

    def test_early_failure_cannot_win_with_short_exposure(self):
        result=self.evaluate([row(0.),row(1.,ok=0.,outage=1.,ratio=.01)])
        self.assertIn('lost_baseline_success',result['decisions']['1.0']['failures'])
        self.assertIsNone(result['selected_lambda'])

    def test_ratio_drop_with_absolute_increase_fails(self):
        result=self.evaluate([row(0.),row(1.,outage=25.,ratio=.25)])
        self.assertIn('insufficient_absolute_outage_reduction',result['decisions']['1.0']['failures'])

    def test_partial_and_incomplete_coverage_fail(self):
        broken=row(1.,outage=1.);broken['summary']['error']='parse failure'
        self.assertIsNone(self.evaluate([row(0.),broken])['selected_lambda'])
        self.assertIsNone(self.evaluate([row(0.)])['selected_lambda'])

    def test_zero_baseline_is_undefined_not_infinite_gain(self):
        result=self.evaluate([row(0.,outage=0.),row(1.,outage=0.)])
        self.assertIn('zero_baseline_outage',result['decisions']['1.0']['failures'])


if __name__=='__main__':unittest.main()
