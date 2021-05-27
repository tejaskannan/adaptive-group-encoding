"""
This file implements Skip RNN Cells for Adaptive Sampling. The classes here
are from the following repository and associated paper:

Paper: https://arxiv.org/abs/1708.06834
Repo: https://github.com/imatge-upc/skiprnn-2017-telecombcn/blob/master/src/rnn_cells/skip_rnn_cells.py.
"""
import tensorflow as tf
import numpy as np
from collections import namedtuple, defaultdict
from sklearn.metrics import mean_absolute_error
from typing import Optional, Any, Dict, Tuple

from adaptiveleak.utils.constants import SMALL_NUMBER
from adaptiveleak.server import reconstruct_sequence
from neural_network import NeuralNetwork, PREDICTION_OP, LOSS_OP, INPUTS
from tfutils import apply_noise


START_LOSS_WEIGHT = 0.01
LOSS_WEIGHT = 'loss_weight'


SkipRNNStateTuple = namedtuple('SkipUGRNNStateTuple', ['state', 'prev_input', 'cumulative_state_update'])
SkipRNNOutputTuple = namedtuple('SkipUGRNNOutputTuple', ['output', 'state_update_gate', 'gate_value'])


def binarize(x: tf.Tensor, name: str = 'binarize') -> tf.Tensor:
    """
    Maps the values in the given tensor to {0, 1} using a rounding function. This function
    assigns the gradient to be the identity.
    """
    g = tf.compat.v1.get_default_graph()

    with g.gradient_override_map({'Round': 'Identity'}):
        return tf.round(x, name=name)


class SkipGRUCell(tf.compat.v1.nn.rnn_cell.RNNCell):

    def __init__(self, units: int, input_size: int, name: str):
        self._units = units
        self._input_size = input_size

        # Make the trainable variables for this cell
        with tf.compat.v1.variable_scope(name):
            self.W_gates = tf.compat.v1.get_variable(name='W-gates',
                                                     initializer=tf.compat.v1.glorot_uniform_initializer(),
                                                     shape=[units + input_size, 2 * units],
                                                     trainable=True)
            self.b_gates = tf.compat.v1.get_variable(name='b-gates',
                                                     initializer=tf.compat.v1.glorot_uniform_initializer(),
                                                     shape=[1, 2 * units],
                                                     trainable=True)
            
            self.W_candidate = tf.compat.v1.get_variable(name='W-candidate',
                                                         initializer=tf.compat.v1.glorot_uniform_initializer(),
                                                         shape=[units + input_size, units],
                                                         trainable=True)
            self.b_candidate = tf.compat.v1.get_variable(name='b-candidate',
                                                         initializer=tf.compat.v1.glorot_uniform_initializer(),
                                                         shape=[1, units],
                                                         trainable=True)
            
            self.W_state = tf.compat.v1.get_variable(name='W-state',
                                                     initializer=tf.compat.v1.glorot_uniform_initializer(),
                                                     shape=[units, 1],
                                                     trainable=True)
            self.b_state = tf.compat.v1.get_variable(name='b-state',
                                                     initializer=tf.compat.v1.glorot_uniform_initializer(),
                                                     shape=[1, 1],
                                                     trainable=True)

    @property
    def state_size(self) -> SkipRNNStateTuple:
        return SkipRNNStateTuple(self._units, self._input_size, 1)

    @property
    def output_size(self) -> SkipRNNOutputTuple:
        return SkipRNNOutputTuple(self._input_size, 1, 1)

    def get_initial_state(self, inputs: Optional[tf.Tensor], batch_size: Optional[int], dtype: Any) -> SkipRNNStateTuple:
        """
        Creates an initial state by setting the hidden state to zero and the update probability to 1.
        """
        initial_state = tf.compat.v1.get_variable(name='initial-hidden-state',
                                                  initializer=tf.compat.v1.zeros_initializer(),
                                                  shape=[1, self._units],
                                                  dtype=dtype,
                                                  trainable=False)

        initial_prev_input = tf.compat.v1.get_variable(name='initial-prev-input',
                                                  initializer=tf.compat.v1.zeros_initializer(),
                                                  shape=[1, self._input_size],
                                                  dtype=dtype,
                                                  trainable=False)

        initial_state_update_prob = tf.compat.v1.get_variable(name='initial-state-update-prob',
                                                              initializer=tf.compat.v1.ones_initializer(),
                                                              shape=[1, 1],
                                                              dtype=dtype,
                                                              trainable=False)

        # We tile the initial states across the entire batch
        return SkipRNNStateTuple(state=tf.tile(initial_state, multiples=(batch_size, 1)),
                                 prev_input=tf.tile(initial_prev_input, multiples=(batch_size, 1)),
                                 cumulative_state_update=tf.tile(initial_state_update_prob, multiples=(batch_size, 1)))

    def __call__(self, inputs: tf.Tensor, state: SkipRNNStateTuple, scope=None) -> Tuple[SkipRNNOutputTuple, SkipRNNStateTuple]:
        # Unpack the previous state
        prev_state, prev_input, prev_cum_state_update_prob = state

        scope = scope if scope is not None else type(self).__name__
        with tf.compat.v1.variable_scope(scope):
            # Apply the standard GRU update, [B, D]
            stacked = tf.concat([inputs, prev_state], axis=-1)
            gates = tf.math.sigmoid(tf.matmul(stacked, self.W_gates) + self.b_gates)

            # Pair of [B, D] tensors
            update_gate, reset_gate = tf.split(gates, num_or_size_splits=2, axis=-1)

            # Stack the features after applying the reset gate and compute the candidate state, [B, D]
            stacked = tf.concat([inputs, tf.multiply(prev_state, reset_gate)], axis=-1)
            candidate = tf.nn.tanh(tf.matmul(stacked, self.W_candidate) + self.b_candidate)

            next_cell_state = tf.multiply(update_gate, candidate) + tf.multiply(1.0 - update_gate, prev_state)

            # Apply a small amount of noise for regularization
            next_cell_state = apply_noise(next_cell_state, scale=0.01)

            # Apply the state update gate. This is the Skip portion.
            # We first compute the state update gate. This is a binary version of the cumulative state update prob.
            state_update_gate = binarize(prev_cum_state_update_prob)  # A [B, 1] binary tensor

            # Apply the binary state update gate to get the next state, [B, D]
            next_state = state_update_gate * next_cell_state + (1 - state_update_gate) * prev_state
            next_input = state_update_gate * inputs + (1 - state_update_gate) * prev_input

            # Compute the next state update probability (clipped into the range [0, 1])
            delta_state_update_prob = tf.math.sigmoid(tf.matmul(next_state, self.W_state) + self.b_state)  # [B, 1]
            cum_prob_candidate = prev_cum_state_update_prob + tf.minimum(delta_state_update_prob, 1.0 - prev_cum_state_update_prob)
            cum_state_update_prob = state_update_gate * delta_state_update_prob + (1 - state_update_gate) * cum_prob_candidate

            skip_state = SkipRNNStateTuple(next_state, next_input, cum_state_update_prob)
            skip_output = SkipRNNOutputTuple(next_input, state_update_gate, delta_state_update_prob)

        return skip_output, skip_state


class SkipRNN(NeuralNetwork):

    @property
    def target(self) -> float:
        return float(self._hypers['target'])

    @property
    def seq_length(self) -> int:
        return self.input_shape[0]

    @property
    def name(self) -> float:
        return '{0}-{1}'.format(self._name, int(self.target * 100))

    @property
    def loss_weight(self) -> float:
        return self._hypers['update_weight']

    def batch_to_feed_dict(self, features: np.ndarray, epoch: int, is_train: bool) -> Dict[tf.compat.v1.placeholder, np.ndarray]:
        feed_dict = super().batch_to_feed_dict(features=features, epoch=epoch, is_train=is_train)
    
        if (epoch >= self.warmup):
            loss_weight = self.loss_weight
        else:
            alpha = (1.0 / self.warmup) * np.log(self.loss_weight / START_LOSS_WEIGHT)
            loss_weight = START_LOSS_WEIGHT * np.exp(alpha * epoch)

        feed_dict[self._placeholders[LOSS_WEIGHT]] = loss_weight

        return feed_dict

    def make_placeholders(self):
        """
        Creates the placeholders for this model.
        """
        super().make_placeholders()

        self._placeholders[LOSS_WEIGHT] = tf.compat.v1.placeholder(shape=(),
                                                                   dtype=tf.float32,
                                                                   name=LOSS_WEIGHT)

    def make_graph(self, is_train: bool):
        inputs = self._placeholders[INPUTS]  # [B, T, D]

        # Create the RNN Cell
        rnn_cell = SkipGRUCell(units=self._hypers['rnn_units'],
                               input_size=self.input_shape[-1],
                               name='rnn-cell')

        initial_state = rnn_cell.get_initial_state(inputs=inputs,
                                                   batch_size=tf.shape(inputs)[0],
                                                   dtype=tf.float32)

        # Apply the RNN Cell [B, T, D]
        rnn_output, _ = tf.compat.v1.nn.dynamic_rnn(cell=rnn_cell,
                                                    inputs=inputs,
                                                    initial_state=initial_state,
                                                    dtype=tf.float32)

        # Extract the output values
        predictions = rnn_output.output
        skip_gates = tf.squeeze(rnn_output.state_update_gate, axis=-1)

        self._ops[PREDICTION_OP] = predictions
        self._ops['skip_gates'] = skip_gates

    def make_loss(self):
        prediction = self._ops[PREDICTION_OP]
        expected = self._placeholders[INPUTS]

        squared_diff = tf.square(prediction - expected)
        pred_loss = tf.reduce_mean(squared_diff)

        num_updates = tf.reduce_sum(self._ops['skip_gates'], axis=-1)  # [B]
        update_rate = num_updates / self.seq_length  # [B]
        avg_update_rate = tf.reduce_mean(update_rate)
        update_diff = avg_update_rate - self.target

        update_loss = self._placeholders[LOSS_WEIGHT] * tf.math.maximum(update_diff, -0.1 * update_diff)

        self._ops[LOSS_OP] = pred_loss + update_loss

    def reconstruct(self, inputs: np.ndarray, labels: np.ndarray) -> Tuple[float, float, Dict[str, Tuple[float, float]]]:
        # Compute the skip gates, [N, T]
        feed_dict = self.batch_to_feed_dict(inputs, epoch=self.warmup, is_train=False)
        model_result = self.execute('skip_gates', feed_dict=feed_dict)
        skip_gates = model_result['skip_gates']

        errors: List[float] = []
        num_collected: List[float] = []

        label_sizes: DefaultDict[int, List[int]] = defaultdict(list)

        for gates, seq_inputs, label in zip(skip_gates, inputs, labels):
            collected_indices = [idx for idx in range(self.seq_length) if np.isclose(gates[idx], 1)]
            measurements = seq_inputs[collected_indices]

            reconstructed = reconstruct_sequence(measurements=measurements,
                                                 collected_indices=collected_indices,
                                                 seq_length=self.seq_length)

            error = mean_absolute_error(y_true=seq_inputs,
                                        y_pred=reconstructed)

            errors.append(error)
            num_collected.append(len(collected_indices))

            label_sizes[label].append(len(collected_indices))

        avg_error = np.average(errors)
        collection_rate = np.average(num_collected) / self.seq_length

        label_stats: Dict[str, Tuple[float, float]] = dict()
        for label in label_sizes.keys():
            avg_size = np.average(label_sizes[label])
            std_size = np.std(label_sizes[label])
            label_stats[str(label)] = (float(avg_size), float(std_size))

        return avg_error, collection_rate, label_stats
