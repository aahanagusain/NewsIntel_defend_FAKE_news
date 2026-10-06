"""
dEFEND: Explainable Fake News Detection Architecture
Based on KDD 2019 Paper by Kai Shu et al.

Components:
1. Word Embedding Layer
2. Sentence BiLSTM Encoder
3. Comment BiLSTM Encoder
4. Sentence-Comment Co-Attention Memory Matrix & Weight Calculator
5. Classification Head (Fake / Real)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Tuple, List


class CoAttention(nn.Module):
    """
    Sentence-Comment Co-Attention Mechanism (dEFEND, KDD 2019).
    Calculates joint attention between article sentences and user comments.
    """
    def __init__(self, feature_dim: int, attention_dim: int):
        super(CoAttention, self).__init__()
        self.feature_dim = feature_dim
        self.attention_dim = attention_dim

        # Projection matrices
        self.W_s = nn.Linear(feature_dim, attention_dim, bias=False)
        self.W_c = nn.Linear(feature_dim, attention_dim, bias=False)
        self.W_memory = nn.Parameter(torch.Tensor(attention_dim, attention_dim))
        
        self.w_hs = nn.Linear(attention_dim, 1, bias=False)
        self.w_hc = nn.Linear(attention_dim, 1, bias=False)

        nn.init.xavier_uniform_(self.W_memory)

    def forward(self, sentence_encs: torch.Tensor, comment_encs: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Args:
            sentence_encs: (batch_size, n_sentences, feature_dim)
            comment_encs: (batch_size, n_comments, feature_dim)

        Returns:
            doc_repr: (batch_size, feature_dim)
            comm_repr: (batch_size, feature_dim)
            alpha (sentence_weights): (batch_size, n_sentences)
            beta (comment_weights): (batch_size, n_comments)
        """
        batch_size, n_s, _ = sentence_encs.size()
        _, n_c, _ = comment_encs.size()

        # Project features into attention space
        S_proj = self.W_s(sentence_encs)  # (batch_size, n_s, att_dim)
        C_proj = self.W_c(comment_encs)   # (batch_size, n_c, att_dim)

        # Affinity memory matrix L = tanh(S * W_memory * C^T)
        M_s = torch.matmul(S_proj, self.W_memory) # (batch, n_s, att_dim)
        L = torch.tanh(torch.matmul(M_s, C_proj.transpose(1, 2))) # (batch, n_s, n_c)

        # Sentence Attention H_s = tanh(S_proj + C_proj * L^T)
        C_summary = torch.matmul(L, C_proj) # (batch, n_s, att_dim)
        H_s = torch.tanh(S_proj + C_summary) # (batch, n_s, att_dim)
        alpha_logits = self.w_hs(H_s).squeeze(-1) # (batch, n_s)
        alpha = F.softmax(alpha_logits, dim=-1) # (batch, n_s)

        # Comment Attention H_c = tanh(C_proj + S_proj * L)
        S_summary = torch.matmul(L.transpose(1, 2), S_proj) # (batch, n_c, att_dim)
        H_c = torch.tanh(C_proj + S_summary) # (batch, n_c, att_dim)
        beta_logits = self.w_hc(H_c).squeeze(-1) # (batch, n_c)
        beta = F.softmax(beta_logits, dim=-1) # (batch, n_c)

        # Compute weighted document and comment representations
        doc_repr = torch.matmul(alpha.unsqueeze(1), sentence_encs).squeeze(1) # (batch, feature_dim)
        comm_repr = torch.matmul(beta.unsqueeze(1), comment_encs).squeeze(1)  # (batch, feature_dim)

        return doc_repr, comm_repr, alpha, beta


class DEFENDModel(nn.Module):
    """
    Complete dEFEND Architecture:
    Word Embeddings -> Sentence/Comment BiLSTMs -> Co-Attention -> Classifier
    """
    def __init__(self, vocab_size: int = 5000, embed_dim: int = 100, hidden_dim: int = 64, att_dim: int = 64):
        super(DEFENDModel, self).__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        
        # Word-to-Sentence BiLSTM
        self.sentence_bilstm = nn.LSTM(
            input_size=embed_dim,
            hidden_size=hidden_dim,
            num_layers=1,
            batch_first=True,
            bidirectional=True
        )

        # Word-to-Comment BiLSTM
        self.comment_bilstm = nn.LSTM(
            input_size=embed_dim,
            hidden_size=hidden_dim,
            num_layers=1,
            batch_first=True,
            bidirectional=True
        )

        feature_dim = hidden_dim * 2
        self.co_attention = CoAttention(feature_dim=feature_dim, attention_dim=att_dim)

        # Classification Head
        self.classifier = nn.Sequential(
            nn.Linear(feature_dim * 2, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 2)
        )

    def _encode_units(self, unit_tensor: torch.Tensor, lstm_layer: nn.LSTM) -> torch.Tensor:
        """
        Encode batch of sentences/comments.
        unit_tensor: (batch_size, num_units, seq_len)
        """
        batch_size, num_units, seq_len = unit_tensor.size()
        flat_input = unit_tensor.view(-1, seq_len) # (batch_size * num_units, seq_len)
        embeds = self.embedding(flat_input)        # (batch_size * num_units, seq_len, embed_dim)

        out, (hn, _) = lstm_layer(embeds)          # out: (batch*num_units, seq_len, 2*hidden_dim)
        unit_encs = out.mean(dim=1)                # (batch_size * num_units, 2*hidden_dim)
        return unit_encs.view(batch_size, num_units, -1) # (batch_size, num_units, 2*hidden_dim)

    def forward(self, sentences: torch.Tensor, comments: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        sentences: (batch_size, max_sentences, max_words)
        comments: (batch_size, max_comments, max_words)
        """
        sentence_encs = self._encode_units(sentences, self.sentence_bilstm)
        comment_encs = self._encode_units(comments, self.comment_bilstm)

        doc_repr, comm_repr, alpha, beta = self.co_attention(sentence_encs, comment_encs)

        combined_repr = torch.cat([doc_repr, comm_repr], dim=-1) # (batch_size, feature_dim * 2)
        logits = self.classifier(combined_repr)                  # (batch_size, 2)
        probs = F.softmax(logits, dim=-1)

        return {
            'logits': logits,
            'probabilities': probs,
            'sentence_attention': alpha,
            'comment_attention': beta
        }


if __name__ == '__main__':
    model = DEFENDModel(vocab_size=1000, embed_dim=50, hidden_dim=32, att_dim=32)
    sample_s = torch.randint(0, 1000, (2, 5, 10))
    sample_c = torch.randint(0, 1000, (2, 3, 10))
    res = model(sample_s, sample_c)
    print("dEFEND Model Test Output:")
    print("Logits shape:", res['logits'].shape)
    print("Sentence attention shape:", res['sentence_attention'].shape)
    print("Comment attention shape:", res['comment_attention'].shape)
