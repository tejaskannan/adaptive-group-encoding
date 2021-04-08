import numpy as np
import math
import os.path
from collections import deque
from enum import Enum, auto
from typing import Tuple, List, Dict, Any

from adaptiveleak.controllers import PIDController
from adaptiveleak.utils.constants import BIT_WIDTH, MIN_WIDTH
from adaptiveleak.utils.data_utils import get_group_widths, get_num_groups, calculate_bytes, pad_to_length
from adaptiveleak.utils.data_utils import prune_sequence, get_max_collected, calculate_grouped_bytes, linear_extrapolate
from adaptiveleak.utils.message import encode_byte_measurements, decode_byte_measurements
from adaptiveleak.utils.message import encode_grouped_measurements, decode_grouped_measurements
from adaptiveleak.utils.encryption import AES_BLOCK_SIZE, EncryptionMode, CHACHA_NONCE_LEN
from adaptiveleak.utils.file_utils import read_json, read_pickle_gz


MARGIN = 0.005


class EncodingMode(Enum):
    STANDARD = auto()
    GROUP = auto()


class Policy:

    def __init__(self,
                 target: float,
                 precision: int,
                 width: int,
                 num_features: int,
                 seq_length: int,
                 encryption_mode: EncryptionMode):
        self._estimate = np.zeros((num_features, 1))  # [D, 1]
        self._precision = precision
        self._width = width
        self._num_features = num_features
        self._seq_length = seq_length
        self._target = target
        self._encryption_mode = encryption_mode

        self._rand = np.random.RandomState(seed=78362)

        # Track the average number of measurements sent
        self._measurement_count = 0
        self._seq_count = 0

    @property
    def width(self) -> int:
        return self._width

    @property
    def precision(self) -> int:
        return self._precision

    @property
    def seq_length(self) -> int:
        return self._seq_length

    @property
    def num_features(self) -> int:
        return self._num_features

    @property
    def target(self) -> float:
        return self._target

    @property
    def encryption_mode(self) -> EncryptionMode:
        return self._encryption_mode

    def collect(self, measurement: np.ndarray):
        self._estimate = np.copy(measurement.reshape(-1, 1))
    
    def reset(self):
        self._estimate = np.zeros((self._num_features, 1))  # [D, 1]

    def encode(self, measurements: np.ndarray, collected_indices: List[int]) -> bytes:
        return encode_byte_measurements(measurements=measurements,
                                        collected_indices=collected_indices,
                                        seq_length=self.seq_length,
                                        precision=self.precision)

    def decode(self, message: bytes) -> Tuple[np.ndarray, List[int]]:
        return decode_byte_measurements(byte_str=message,
                                        seq_length=self.seq_length,
                                        num_features=self.num_features)

    def step(self, count: int, seq_idx: int):
        self._measurement_count += count
        self._seq_count += 1

    def __str__(self) -> str:
        return 'Policy'

    def as_dict(self) -> Dict[str, Any]:
        return {
            'name': str(self),
            'target': self.target,
            'width': self.width,
            'precision': self.precision,
            'encryption_mode': self._encryption_mode.name
        }

    def should_collect(self, seq_idx: int) -> bool:
        raise NotImplementedError()


class AdaptivePolicy(Policy):

    def __init__(self,
                 target: float,
                 threshold: float,
                 precision: int,
                 width: int,
                 seq_length: int,
                 num_features: int,
                 encryption_mode: EncryptionMode,
                 encoding_mode: EncodingMode):
        super().__init__(precision=precision,
                         width=width,
                         target=target,
                         num_features=num_features,
                         seq_length=seq_length,
                         encryption_mode=encryption_mode)

        # Name of the encoding algorithm
        self._encoding_mode = encoding_mode

        # Variables used to track the adaptive sampling policy
        self._max_skip = int(1.0 / target) + 1
        self._current_skip = 0
        self._sample_skip = 0

        # Controller automatically set the threshold
        #self._pid = PIDController(kp=(1.0 / 16.0),
        #                          ki=(1.0 / 32.0),
        #                          kd=(1.0 / 128.0))

        self._threshold = threshold

    @property
    def encoding_mode(self) -> EncodingMode:
        return self._encoding_mode

    @property
    def group_size(self) -> int:
        return max(int(math.ceil((BIT_WIDTH * AES_BLOCK_SIZE) / self.num_features)), 1)

    def reset(self):
        super().reset()
        self._current_skip = 0
        self._sample_skip = 0

    #def step(self, count: int, seq_idx: int):
    #    super().step(count=count, seq_idx=seq_idx)

    #    avg = self._measurement_count / (self._seq_count * self._seq_length)
    #    signal = self._pid.step(estimate=avg, target=self._target)

    #    #if ((seq_idx + 1) % self._window) == 0:
    #    #    self._threshold = max(self._start_threshold - signal, 0.0)

    def encode(self, measurements: np.ndarray, collected_indices: List[int]) -> bytes:
        if self.encoding_mode == EncodingMode.STANDARD:
            return super().encode(measurements, collected_indices)
        elif self.encoding_mode == EncodingMode.GROUP:
            num_collected = len(measurements)

            # Get the group widths
            num_groups = get_num_groups(num_collected=num_collected,
                                        group_size=self.group_size)

            widths = get_group_widths(group_size=self.group_size,
                                      num_collected=num_collected,
                                      num_features=self.num_features,
                                      seq_length=self.seq_length,
                                      target_frac=self.target,
                                      encryption_mode=self.encryption_mode)

            # Get the maximum possible number of collected measurements
            target_bytes = calculate_bytes(width=BIT_WIDTH,
                                           num_collected=int(self.target * self.seq_length),
                                           num_features=self.num_features,
                                           seq_length=self.seq_length,
                                           encryption_mode=self.encryption_mode)

            max_collected = get_max_collected(seq_length=self.seq_length,
                                              num_features=self.num_features,
                                              group_size=self.group_size,
                                              min_width=MIN_WIDTH,
                                              target_size=target_bytes,
                                              encryption_mode=self.encryption_mode)

            # Prune away any excess measurements
            measurements, collected_indices = prune_sequence(measurements=measurements,
                                                             collected_indices=collected_indices,
                                                             max_collected=max_collected)

            # Encode the measurement values
            non_fractional = self.width - self.precision
            encoded = encode_grouped_measurements(measurements=measurements,
                                                  collected_indices=collected_indices,
                                                  seq_length=self.seq_length,
                                                  widths=widths,
                                                  non_fractional=non_fractional,
                                                  group_size=self.group_size)

            expected_bytes = calculate_grouped_bytes(widths=widths,
                                                     num_collected=num_collected,
                                                     num_features=self.num_features,
                                                     group_size=self.group_size,
                                                     seq_length=self.seq_length,
                                                     encryption_mode=self.encryption_mode)

            if self.encryption_mode == EncryptionMode.STREAM:
                return pad_to_length(encoded, length=target_bytes - CHACHA_NONCE_LEN)

            return encoded
        else:
            raise ValueError('Unknown encoding type {0}'.format(self.encoding_mode.name))

    def decode(self, message: bytes) -> Tuple[np.ndarray, List[int]]:
        if self.encoding_mode == EncodingMode.STANDARD:
            return super().decode(message)
        elif self.encoding_mode == EncodingMode.GROUP:
            non_fractional = self.width - self.precision

            return decode_grouped_measurements(encoded=message,
                                               seq_length=self.seq_length,
                                               num_features=self.num_features,
                                               non_fractional=non_fractional,
                                               group_size=self.group_size)
        else:
            raise ValueError('Unknown encoding type {0}'.format(self.encoding_mode.name))

    def __str__(self) -> str:
        return 'adaptive_{0}'.format(self._encoding_mode.name.lower())

    def as_dict(self) -> Dict[str, Any]:
        policy_dict = super().as_dict()
        policy_dict['encoding'] = self._encoding_mode.name
        return policy_dict


class AdaptiveHeuristic(AdaptivePolicy):

    def should_collect(self, seq_idx: int) -> bool:
        if self._sample_skip > 0:
            self._sample_skip -= 1
            return False

        return True

    def collect(self, measurement: np.ndarray):
        diff = np.sum(np.abs(self._estimate - measurement))
        self._estimate = measurement

        if diff > self._threshold:
            self._current_skip = 0
        else:
            self._current_skip = min(self._current_skip + 1, self._max_skip)

        self._sample_skip = self._current_skip

    def __str__(self) -> str:
        return 'adaptive_heuristic_{0}'.format(self._encoding_mode.name.lower())


class AdaptiveLiteSense(AdaptivePolicy):

    def __init__(self,
                 target: float,
                 threshold: float,
                 precision: int,
                 width: int,
                 seq_length: int,
                 num_features: int,
                 encryption_mode: EncryptionMode,
                 encoding_mode: EncodingMode):
        super().__init__(target=target,
                         threshold=threshold,
                         precision=precision,
                         width=width,
                         seq_length=seq_length,
                         num_features=num_features,
                         encryption_mode=encryption_mode,
                         encoding_mode=encoding_mode)
        self._alpha = 0.7
        self._beta = 0.7

        self._mean = np.zeros(shape=(num_features, 1))  # [D, 1]
        self._dev = np.zeros(shape=(num_features, 1))

    def should_collect(self, seq_idx: int) -> bool:
        if (seq_idx == 0) or (self._sample_skip >= self._current_skip):
            return True

        self._sample_skip += 1
        return False

    def collect(self, measurement: np.ndarray):
        updated_mean = (1.0 - self._alpha) * self._mean + self._alpha * measurement
        updated_dev = (1.0 - self._beta) * self._dev + self._beta * np.abs(updated_mean - measurement)

        diff = np.sum(updated_dev - self._dev)

        if diff > self._threshold:
            self._current_skip = max(self._current_skip - 1 if diff < 1.0 else 0, 0)
        else:
            self._current_skip = min(self._current_skip + 1, self._max_skip)

        self._estimate = measurement

        self._mean = updated_mean
        self._dev = updated_dev

        self._sample_skip = 0

    def reset(self):
        super().reset()
        self._mean = np.zeros(shape=(self.num_features, 1))  # [D, 1]
        self._dev = np.zeros(shape=(self.num_features, 1))

    def __str__(self) -> str:
        return 'adaptive_litesense_{0}'.format(self._encoding_mode.name.lower())


class AdaptiveJitter(AdaptivePolicy):

    def __init__(self,
                 target: float,
                 threshold: float,
                 precision: int,
                 width: int,
                 seq_length: int,
                 num_features: int,
                 encryption_mode: EncryptionMode,
                 encoding_mode: EncodingMode):
        super().__init__(target=target,
                         threshold=threshold,
                         precision=precision,
                         width=width,
                         seq_length=seq_length,
                         num_features=num_features,
                         encryption_mode=encryption_mode,
                         encoding_mode=encoding_mode)
        self._prev = np.zeros(shape=(num_features, 1))  # [D, 1]

    def should_collect(self, seq_idx: int) -> bool:
        if (seq_idx > 0) and (self._sample_skip < self._current_skip):
            self._sample_skip += 1
            return False

        return True

    def collect(self, measurement: np.ndarray):
        self._prev = self._estimate
        self._estimate = measurement

        slope = (self._estimate - self._prev) / (self._current_skip + 1)
        slope_norm = np.sum(np.abs(slope))
        num_steps = self._threshold / (slope_norm + 1e-5)

        self._current_skip = min(int(num_steps), self._max_skip)

        self._sample_skip = 0

    def reset(self):
        super().reset()
        self._prev = np.zeros(shape=(self.num_features, 1))


class RandomPolicy(Policy):

    def should_collect(self, seq_idx: int) -> bool:
        r = self._rand.uniform()

        if r < self._target or seq_idx == 0:
            return True

        return False

    def __str__(self) -> str:
        return 'random'


class UniformPolicy(Policy):
    
    def __init__(self,
                 target: float,
                 precision: int,
                 width: int,
                 seq_length: int,
                 num_features: int,
                 encryption_mode: EncryptionMode):
        super().__init__(precision=precision,
                         width=width,
                         target=target,
                         num_features=num_features,
                         seq_length=seq_length,
                         encryption_mode=encryption_mode)
        target_samples = int(math.ceil(target * seq_length))

        skip = max(1.0 / target, 1)
        frac_part = skip - math.floor(skip)

        self._skip_indices: List[int] = []

        index = 0
        while index < seq_length:
            self._skip_indices.append(index)

            if (target_samples - len(self._skip_indices)) == (seq_length - index - 1):
                index += 1
            else:
                r = self._rand.uniform()
                if r > frac_part:
                    index += int(math.floor(skip))
                else:
                    index += int(math.ceil(skip))

        self._skip_indices = self._skip_indices[:target_samples]
        self._skip_idx = 0

    def should_collect(self, seq_idx: int) -> bool:
        if (seq_idx == 0) or (self._skip_idx < len(self._skip_indices) and seq_idx == self._skip_indices[self._skip_idx]):
            self._skip_idx += 1
            return True

        return False

    def __str__(self) -> str:
        return 'uniform'

    def reset(self):
        super().reset()
        self._skip_idx = 0


def run_policy(policy: Policy, sequence: np.ndarray) -> Tuple[np.ndarray, List[int]]:
    """
    Executes the policy on the given sequence.

    Args:
        policy: The sampling policy
        sequence: A [T, D] array of features (D) for each element (T)
    Returns:
        A tuple of two elements:
            (1) A [K, D] array of the collected measurements
            (2) The K indices of the collected elements
    """
    assert len(sequence.shape) == 2, 'Must provide a 2d sequence'

    collected_list: List[np.ndarray] = []
    collected_indices: List[int] = []

    for seq_idx in range(sequence.shape[0]):
        
        should_collect = policy.should_collect(seq_idx=seq_idx)

        if should_collect:
            measurement = sequence[seq_idx]
            policy.collect(measurement=measurement)

            collected_list.append(measurement.reshape(1, -1))
            collected_indices.append(seq_idx)

    return np.vstack(collected_list), collected_indices


def make_policy(name: str, seq_length: int, num_features: int, encryption_mode: EncryptionMode, target: float, dataset: str, **kwargs: Dict[str, Any]) -> Policy:
    name = name.lower()

    # Look up the data-specific precision
    precision_path = os.path.join('datasets', dataset, 'quantize.json')
    precision_dict = read_json(precision_path)
    precision = precision_dict['precision']

    if name == 'random':
        return RandomPolicy(target=target + MARGIN,
                            precision=precision,
                            width=BIT_WIDTH,
                            num_features=num_features,
                            seq_length=seq_length,
                            encryption_mode=encryption_mode)
    elif name == 'uniform':
        return UniformPolicy(target=target + MARGIN,
                             precision=precision,
                             width=BIT_WIDTH,
                             num_features=num_features,
                             seq_length=seq_length,
                             encryption_mode=encryption_mode)
    elif name.startswith('adaptive'):
        # Look up the threshold path
        threshold_path = os.path.join('saved_models', dataset, 'thresholds.pkl.gz')

        if not os.path.exists(threshold_path):
            print('WARNING: No threshold path exists. Defaulting to 0.0')
            threshold = 0.0
        else:
            thresholds = read_pickle_gz(threshold_path)

            if (name not in thresholds) or (target not in thresholds[name]):
                print('WARNING: No threshold path exists. Defaulting to 0.0')
                threshold = 0.0
            else:
                threshold = thresholds[name][target]

        if name == 'adaptive_heuristic':
            cls = AdaptiveHeuristic
        elif name == 'adaptive_litesense':
            cls = AdaptiveLiteSense
        elif name == 'adaptive_jitter':
            cls = AdaptiveJitter
        else:
            raise ValueError('Unknown adaptive policy with name: {0}'.format(name))

        return cls(target=target,
                   threshold=threshold,
                   precision=precision,
                   width=BIT_WIDTH,
                   seq_length=seq_length,
                   num_features=num_features,
                   encryption_mode=encryption_mode,
                   encoding_mode=EncodingMode[str(kwargs['encoding']).upper()])
    else:
        raise ValueError('Unknown policy with name: {0}'.format(name))
