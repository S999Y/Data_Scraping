"""
Research-area topic inference.

Maps free text (interests, paper titles, abstracts, department names) onto a
fixed set of research-area tags so every professor can be compared with the
same vocabulary in the recommendation stage.

Tag vocabulary:
    ML, AI, NLP, CV, Cybersecurity, Data Mining, IoT, Robotics,
    Bioinformatics, Blockchain, Cloud Computing, HCI, Systems, Theory
"""

import re

TOPIC_KEYWORDS = {
    'ML': ['machine learning', 'deep learning', 'neural network', 'reinforcement learning',
           'learning algorithms', 'unsupervised learning', 'supervised learning',
           'representation learning', 'gradient boosting', 'random forest', 'svm',
           'kernel methods', 'bayesian inference', 'probabilistic model',
           'generative model', 'diffusion model', 'transformer', 'gpt', 'llm',
           'language model', 'foundation model', 'fine-tuning', 'classification'],
    'AI': ['artificial intelligence', 'artificial intelligent', 'intelligent agent',
           'knowledge representation', 'reasoning', 'automated planning',
           'ai safety', 'artificial agents', 'cognitive science', 'embodied ai'],
    'NLP': ['natural language', 'text mining', 'sentiment analysis', 'speech',
           'summarization', 'machine translation', 'question answering',
           'information extraction', 'language understanding', 'nlp',
           'textual', 'corpus', 'semantic parsing', 'dialogue', 'parsing'],
    'CV': ['computer vision', 'image processing', 'object detection', 'object recognition',
           'image segmentation', 'visual recognition', 'face recognition', 'video analysis',
           'scene understanding', '3d vision', 'medical imaging', 'visual tracking',
           'pattern recognition', 'image generation'],
    'Cybersecurity': ['cybersecurity', 'cyber security', 'security', 'privacy',
           'cryptography', 'encryption', 'network security', 'malware', 'intrusion',
           'adversarial', 'anonymity', 'trusted computing', 'vulnerability', 'authentication'],
    'Data Mining': ['data mining', 'knowledge discovery', 'anomaly detection',
           'clustering', 'association rule', 'predictive analytics', 'data analytics',
           'exploratory data', 'dimensionality reduction', 'data-driven'],
    'IoT': ['internet of things', 'iot', 'embedded system', 'sensor network',
           'smart home', 'wearable', 'cyber-physical system', 'edge computing'],
    'Robotics': ['robotics', 'robot', 'manipulation', 'control system', 'autonomous driving',
           'autonomous vehicle', 'motion planning', 'slam', 'legged', 'mechatronics'],
    'Bioinformatics': ['bioinformatics', 'genomics', 'genomics', 'proteomics',
           'computational biology', 'systems biology', 'drug discovery', 'protein',
           'genome', 'sequencing', 'biomedical', 'dna', 'rna', 'molecule',
           'metabolomics', 'clinical'],
    'Blockchain': ['blockchain', 'distributed ledger', 'smart contract', 'cryptocurrency',
           'bitcoin', 'consensus algorithm'],
    'Cloud Computing': ['cloud computing', 'cloud', 'distributed systems', 'serverless',
           'virtualization', 'container', 'high performance computing', 'parallel computing',
           'data center', 'datacenter', 'storage system'],
    'HCI': ['human-computer', 'human computer interaction', 'user interface',
           'interaction design', 'usability', 'accessibility', 'crowdsourcing',
           'visualization', 'ubiquitous'],
    'Systems': ['operating system', 'systems', 'networking', 'network', 'compiler',
           'database', 'query', 'architecture', 'performance analysis', 'fault tolerance'],
    'Theory': ['theory', 'algorithm', 'computational complexity', 'formal method',
           'graph theory', 'optimization', 'proof', 'automata', 'logic',
           'mathematical'],
}


def infer_topics(text) -> list:
    """
    Return the ordered list of topic tags whose keywords appear in `text`.

    Args:
        text: raw text or iterable of texts (interests, titles, abstracts...).

    Returns:
        List of tag strings, most frequently matched first.
    """
    if not text:
        return []
    if isinstance(text, str):
        chunks = [text]
    else:
        chunks = [str(t) for t in text]
    haystack = ' '.join(chunks).lower()
    haystack = re.sub(r'[\s_]+', ' ', haystack)

    matches = []
    for tag, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw in haystack:
                matches.append(tag)
                break
    return matches


def combine_topics(topic_lists) -> list:
    """Merge several topic lists, preserving frequency order and de-duping."""
    seen = set()
    ordered = []
    for lst in topic_lists:
        for tag in (lst or []):
            if tag not in seen:
                seen.add(tag)
                ordered.append(tag)
    return ordered
