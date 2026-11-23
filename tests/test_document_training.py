import math
import unittest
from auditforge.document_policy import Network, FEATURES, distribution, objective_gradient
from auditforge.document_training import normalize_advantages, actor_critic_targets, DocumentTrainer

class GradientTests(unittest.TestCase):
 def test_linear_and_mlp_gradients_finite_difference(self):
  xs=[[.2*(i%3) for i in range(len(FEATURES))],[-.1*(i%4) for i in range(len(FEATURES))],[0.]*len(FEATURES)]
  xs[-1][-1]=1.
  for architecture in ('linear','mlp'):
   model=Network(architecture,seed=7)
   gradient=objective_gradient(model,xs,1,.7,.03)
   def objective():
    ps=distribution(model,xs)
    return .7*math.log(ps[1])-.03*sum(p*math.log(p) for p in ps)
   for j in range(len(model.parameters)):
    old=model.parameters[j];h=1e-5
    model.parameters[j]=old+h;a=objective()
    model.parameters[j]=old-h;b=objective()
    model.parameters[j]=old
    self.assertAlmostEqual(gradient[j],(a-b)/(2*h),places=6)
 def test_frozen_critic_mc_targets(self):
  a,t=actor_critic_targets(.8,[.1,.3]);self.assertAlmostEqual(a[0],.7);self.assertEqual(a[1],.5);self.assertEqual(t,[.8,.8])
 def test_advantage_normalization_constant_is_finite(self):
  self.assertEqual(normalize_advantages([1.,1.,1.,1.]),[0.,0.,0.,0.])
  v=normalize_advantages([1.,2.,3.,4.]);self.assertAlmostEqual(sum(v),0.)
 def test_checkpoint_rejects_bool_and_nonfinite(self):
  m=DocumentTrainer(seed=7);d=m.checkpoint();d['episodes']=True
  with self.assertRaises(ValueError):DocumentTrainer.from_checkpoint(d)
  d=m.checkpoint();d['parameters'][0]=float('nan')
  with self.assertRaises(ValueError):DocumentTrainer.from_checkpoint(d)
 def test_update_diagnostics_are_gradient_variance_not_advantage_variance(self):
  m=DocumentTrainer(seed=7,normalize_advantage=True)
  for _ in range(4):m.train_episode()
  row=m.history[-1]
  self.assertIn('advantage_variance',row)
  self.assertIn('gradient_variance',row)
  self.assertGreaterEqual(row['gradient_variance'],0)
 def test_checkpoint_rejects_boolean_inspection_steps(self):
  m=DocumentTrainer(seed=7);m.train_episode();d=m.checkpoint()
  d['history'][0]['steps']=2;d['history'][0]['inspection_steps']=True
  with self.assertRaises(ValueError):DocumentTrainer.from_checkpoint(d)
 def test_checkpoint_roundtrip_exact(self):
  m=DocumentTrainer(seed=7,architecture='mlp',normalize_advantage=True,entropy_coefficient=.01)
  self.assertEqual(DocumentTrainer.from_checkpoint(m.checkpoint()).checkpoint(),m.checkpoint())
if __name__=='__main__':unittest.main()
