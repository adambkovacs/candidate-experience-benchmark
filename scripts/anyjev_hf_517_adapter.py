"""Versioned AnyJev HF block-loop adapter for Transformers 5.17.0/Qwen3.

Only the mask construction and decoder-layer calls differ from pinned AnyJev.
The no-cache prefill call mirrors the installed Qwen3Model.forward implementation.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import inspect
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compatibility_evidence():
    """Fail closed if the API whose semantics this adapter mirrors changes."""
    from transformers.masking_utils import create_causal_mask
    from transformers.models.qwen3.modeling_qwen3 import Qwen3DecoderLayer, Qwen3Model

    version = importlib.metadata.version('transformers')
    mask_parameters = list(inspect.signature(create_causal_mask).parameters)
    layer_parameters = list(inspect.signature(Qwen3DecoderLayer.forward).parameters)
    model_parameters = list(inspect.signature(Qwen3Model.forward).parameters)
    if version != '5.17.0':
        raise ValueError('AnyJev HF adapter requires Transformers 5.17.0')
    if mask_parameters[:5] != ['config', 'inputs_embeds', 'attention_mask', 'past_key_values', 'position_ids']:
        raise ValueError('Transformers causal-mask API changed')
    if layer_parameters[:5] != ['self', 'hidden_states', 'attention_mask', 'position_ids', 'past_key_values'] or 'use_cache' not in layer_parameters:
        raise ValueError('Qwen3 decoder-layer API changed')
    if model_parameters[:6] != ['self', 'input_ids', 'attention_mask', 'position_ids', 'past_key_values', 'inputs_embeds']:
        raise ValueError('Qwen3 model forward API changed')
    return {
        'transformers_version': version,
        'masking_utils_sha256': sha(inspect.getfile(create_causal_mask)),
        'modeling_qwen3_sha256': sha(inspect.getfile(Qwen3Model.forward)),
        'causal_mask_parameters': mask_parameters,
        'decoder_layer_parameters': layer_parameters,
        'model_forward_parameters': model_parameters,
    }


def make_517_backend(base):
    """Keep pinned AnyJev's tokenization/capture path, adapt only changed calls."""
    class HF517Backend(base):
        def _prepare(self, enc, pos):
            from transformers.masking_utils import create_causal_mask

            inner = getattr(self.model, 'model', None)
            config = self.model.config
            if (config.model_type != 'qwen3' or inner is None or
                    not hasattr(inner, 'layers') or not hasattr(inner, 'embed_tokens') or
                    not hasattr(inner, 'rotary_emb') or
                    len(inner.layers) != config.num_hidden_layers or
                    set(config.layer_types) != {'full_attention'} or
                    getattr(inner, 'has_sliding_layers', False) or
                    getattr(inner, 'embed_scale', None) is not None):
                raise ValueError('Adapter supports only pinned Qwen3 full-attention layout')
            embeds = inner.embed_tokens(enc['input_ids'])
            # Qwen3Model.forward with use_cache=False passes no cache and these exact
            # arguments to create_causal_mask. The obsolete cache_position is omitted.
            masks = {'full_attention': create_causal_mask(
                config=config, inputs_embeds=embeds,
                attention_mask=enc['attention_mask'], past_key_values=None,
                position_ids=pos)}
            return {'hidden': embeds, 'masks': masks, 'position_ids': pos,
                    'rope': inner.rotary_emb(embeds, pos)}

        def _run_layers(self, ctx, start, stop, capture=None):
            inner = self.model.model
            hidden = ctx['hidden']
            for index in range(start, stop):
                # Match Qwen3Model.forward in Transformers 5.17.0. The pinned
                # AnyJev singular past_key_value kwarg is ignored by this layer.
                result = inner.layers[index](
                    hidden, attention_mask=ctx['masks']['full_attention'],
                    position_embeddings=ctx['rope'],
                    position_ids=ctx['position_ids'],
                    past_key_values=None, use_cache=False)
                hidden = result[0] if isinstance(result, tuple) else result
                if capture is not None:
                    capture(index + 1, hidden)
            ctx['hidden'] = hidden
            ctx['layer'] = stop
            return hidden

    return HF517Backend
