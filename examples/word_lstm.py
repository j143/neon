#!/usr/bin/env python
# ----------------------------------------------------------------------------
# Copyright 2015 Nervana Systems Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ----------------------------------------------------------------------------
"""
Example that trains an LSTM or GRU based recurrent networks.
The dataset uses Penn Treebank dataset parsing on word-level.

Reference:
    Recurrent Neural Network Regularization `[Zaremba2015]`_
    Generating sequences with recurrent neural networks `[Graves2014]`_
.. _[Zaremba2015]: http://arxiv.org/pdf/1409.2329v5.pdf
.. _[Graves2014]: http://arxiv.org/pdf/1308.0850.pdf

Usage:
    python examples/word_lstm.py -e 13 -eval 1 --rlayer_type lstm

"""

from neon.backends import gen_backend
from neon.data import Text, load_text
from neon.initializers import Uniform
from neon.layers import GeneralizedCost, LSTM, Affine, GRU, LookupTable
from neon.models import Model
from neon.optimizers import GradientDescentMomentum, Schedule
from neon.transforms import Logistic, Tanh, Softmax, CrossEntropyMulti
from neon.callbacks.callbacks import Callbacks
from neon.util.argparser import NeonArgparser, extract_valid_args

# parse the command line arguments
parser = NeonArgparser(__doc__)
parser.add_argument('--rlayer_type', default='lstm', choices=['gru', 'lstm'],
                    help='type of recurrent layer to use (gru or lstm)')
args = parser.parse_args(gen_be=False)

# hyperparameters from the reference
args.batch_size = 20
time_steps = 20
hidden_size = 200
gradient_clip_norm = 5

# setup backend
be = gen_backend(**extract_valid_args(args, gen_backend))

# download penn treebank
train_path = load_text('ptb-train', path=args.data_dir)
valid_path = load_text('ptb-valid', path=args.data_dir)


# define a custom function to parse the input into individual tokens, which for
# this data, splits into individual words.  This can be passed into the Text
# object during dataset creation as seen below.
def tokenizer(s):
    return s.replace('\n', '<eos>').split()

# load data and parse on word-level
train_set = Text(time_steps, train_path, tokenizer=tokenizer, onehot_input=False)
valid_set = Text(time_steps, valid_path, vocab=train_set.vocab, tokenizer=tokenizer,
                 onehot_input=False)

# weight initialization
init = Uniform(low=-0.1, high=0.1)

# model initialization
rlayer_params = {"output_size": hidden_size, "init": init,
                 "activation": Tanh(), "gate_activation": Logistic()}
if args.rlayer_type == 'lstm':
    rlayer1, rlayer2 = LSTM(**rlayer_params), LSTM(**rlayer_params)
else:
    rlayer1, rlayer2 = GRU(**rlayer_params), GRU(**rlayer_params)

layers = [
    LookupTable(vocab_size=len(train_set.vocab), embedding_dim=hidden_size, init=init),
    rlayer1,
    rlayer2,
    Affine(len(train_set.vocab), init, bias=init, activation=Softmax())
]

cost = GeneralizedCost(costfunc=CrossEntropyMulti(usebits=True))

model = Model(layers=layers)

# vanilla gradient descent with decay schedule on learning rate and gradient scaling
learning_rate_sched = Schedule(range(5, args.epochs), .5)
optimizer = GradientDescentMomentum(1, 0, gradient_clip_norm=gradient_clip_norm,
                                    schedule=learning_rate_sched)

# configure callbacks
callbacks = Callbacks(model, train_set, eval_set=valid_set, **args.callback_args)

# train model
model.fit(train_set, optimizer=optimizer, num_epochs=args.epochs, cost=cost, callbacks=callbacks)
