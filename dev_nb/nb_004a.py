
        #################################################
        ### THIS FILE WAS AUTOGENERATED! DO NOT EDIT! ###
        #################################################

from nb_004 import *

class OptimWrapper():
    "Basic wrapper around an optimizer to simplify HP changes"
    def __init__(self, opt:optim.Optimizer, wd:Floats=0., true_wd:bool=False):
        self.opt,self.true_wd = opt,true_wd
        self.opt_keys = list(self.opt.param_groups[0].keys())
        self.opt_keys.remove('params')
        self.read_defaults()
        self._wd = self.listify(wd, self.opt.param_groups)

    def __repr__(self) -> str:
        return f'OptimWrapper over {repr(self.opt)}.\nTrue weight decay: {self.true_wd}'

    #Pytorch optimizer methods
    def step(self):
        # weight decay outside of optimizer step (AdamW)
        if self.true_wd:
            for lr,wd,pg in zip(self._lr,self._wd,self.opt.param_groups):
                for p in pg['params']: p.data.mul_(1 - wd*lr)
            self.set_val('weight_decay', 0)
        self.opt.step()

    def zero_grad(self): self.opt.zero_grad()

    #Hyperparameters as properties
    @property
    def lr(self) -> float: return self._lr[-1]

    @lr.setter
    def lr(self, val:float): self._lr = self.set_val('lr', self.listify(val, self._lr))

    @property
    def mom(self) -> float: return self._mom[-1]

    @mom.setter
    def mom(self, val:float):
        if 'momentum' in self.opt_keys: self.set_val('momentum', self.listify(val, self._mom))
        elif 'betas' in self.opt_keys:  self.set_val('betas', (self.listify(val, self._mom), self._beta))
        self._mom = self.listify(val, self._mom)

    @property
    def beta(self) -> float: return None if self._beta is None else self._beta[-1]

    @beta.setter
    def beta(self, val:float):
        if val is None: return
        if 'betas' in self.opt_keys:    self.set_val('betas', (self._mom, self.listify(val, self._beta)))
        elif 'alpha' in self.opt_keys:  self.set_val('alpha', self.listify(val, self._beta))
        self._beta = self.listify(val, self._beta)

    @property
    def wd(self) -> float: return self._wd[-1]

    @wd.setter
    def wd(self, val:float):
        if not self.true_wd: self.set_val('weight_decay', self.listify(val, self._wd))
        self._wd = self.listify(val, self._wd)

    #Helper functions
    def read_defaults(self):
        "Read the values inside the optimizer for the hyper-parameters"
        self._beta = None
        if 'lr' in self.opt_keys: self._lr = self.read_val('lr')
        if 'momentum' in self.opt_keys: self._mom = self.read_val('momentum')
        if 'alpha' in self.opt_keys: self._beta = self.read_val('alpha')
        if 'betas' in self.opt_keys: self._mom,self._beta = self.read_val('betas')
        if 'weight_decay' in self.opt_keys: self._wd = self.read_val('weight_decay')

    def set_val(self, key:str, val):
        "Set the values inside the optimizer dictionary at the key"
        if is_tuple(val): val = [(v1,v2) for v1,v2 in zip(*val)]
        for v,pg in zip(val,self.opt.param_groups): pg[key] = v
        return val

    def read_val(self, key:str) -> Union[List[float],Tuple[List[float],List[float]]]:
        "Read a hyper-parameter key in the optimizer dictionary."
        val = [pg[key] for pg in self.opt.param_groups]
        if is_tuple(val[0]): val = [o[0] for o in val], [o[1] for o in val]
        return val

    def listify(self, p, q) -> List[Any]:
        "Wrap listify with an assert."
        if is_listy(p): assert len(p) == len(q), f'Passing {len(p)} hyperparameters when we have {len(q)} groups.'
        return listify(p,q)

def split_model(model:nn.Module, idx:Sequence[int]) -> List[nn.Module]:
    "Split the model according to the layers index in idx"
    layers = list(model.children())
    if idx[0] != 0: idx = [0] + idx
    if idx[-1] != len(layers): idx.append(len(layers))
    return [nn.Sequential(*layers[i:j]) for i,j in zip(idx[:-1],idx[1:])]

@dataclass
class Learner():
    "Object that wraps together some data, a model, a loss function and an optimizer"

    data:DataBunch
    model:nn.Module
    opt_fn:Callable=optim.SGD
    loss_fn:Callable=F.cross_entropy
    metrics:Collection[Callable]=None
    true_wd:bool=False
    layer_groups:Collection[nn.Module]=None
    def __post_init__(self):
        self.model = self.model.to(self.data.device)
        self.callbacks = []

    def fit(self, epochs:int, lr:Floats, wd:Floats=0., callbacks:Collection[Callback]=None):
        if not hasattr(self, 'opt'): self.create_opt(lr, wd)
        else: self.opt.wd = wd
        if callbacks is None: callbacks = []
        callbacks = self.callbacks + callbacks
        fit(epochs, self.model, self.loss_fn, self.opt, self.data, callbacks=callbacks, metrics=self.metrics)

    def create_opt(self, lr:Floats, wd:Floats=0.):
        if self.layer_groups is None: self.layer_groups = [self.model]
        lrs = listify(lr, self.layer_groups)
        opt = self.opt_fn([{'params':l.parameters(), 'lr':lr} for l,lr in zip(self.layer_groups, lrs)])
        self.opt = OptimWrapper(opt, wd=wd, true_wd=self.true_wd)
        self.recorder = Recorder(self.opt, self.data.train_dl)
        self.callbacks = [self.recorder] + self.callbacks