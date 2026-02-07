import re
import math
from collections import defaultdict

# Bayesian Spam Classifier - Industry Standard Approach
class BayesianSpamDetector:
    """
    Bayesian spam classifier using naive Bayes probability.
    Completely local, private, and free - no external services.
    """
    
    def __init__(self):
        # Spam and ham word frequencies
        self.spam_words = defaultdict(int)
        self.ham_words = defaultdict(int)
        self.total_spam_mails = 0
        self.total_ham_mails = 0
        
        # Pre-trained with common patterns
        self._init_training_data()
    
    def _init_training_data(self):
        """Initialize with pre-trained spam/ham patterns"""
        
        # Common spam indicators (trained on typical spam patterns)
        spam_patterns = {
            # Marketing/Sales
            'buy': 15, 'click': 12, 'offer': 14, 'limited': 11, 'act': 10,
            'deal': 13, 'discount': 12, 'urgent': 10, 'free': 9, 'prize': 14,
            'winner': 15, 'claim': 12, 'congratulations': 13, 'confirm': 8,
            'verify': 9, 'update': 7, 'account': 6, 'suspended': 12,
            
            # Unsubscribe/Marketing
            'unsubscribe': 3, 'newsletter': 2, 'promotional': 8, 'promotion': 8,
            'marketing': 5, 'sale': 7, 'subscribe': 3, 'alert': 2,
            
            # Phishing/Suspicious
            'password': 14, 'reset': 10, 'action': 8, 'required': 8,
            'click here': 15, 'click link': 15, 'urgent action': 12,
            'unusual activity': 11, 'confirm identity': 13, 'update payment': 14,
            
            # Financial
            'money': 10, 'bank': 8, 'credit': 7, 'payment': 5, 'transaction': 3,
            'wire': 12, 'western union': 15, 'paypal': 4,
            
            # Emotional manipulation
            'congratulations': 13, 'amazing': 8, 'incredible': 9, 'fantastic': 8,
            'exclusive': 10, 'limited time': 13, 'act now': 11, 'urgent': 10,
        }
        
        # Common ham indicators (legitimate emails)
        ham_patterns = {
            # Work/Professional
            'meeting': 1, 'project': 1, 'deadline': 1, 'status': 1, 'update': 1,
            'document': 1, 'attached': 1, 'report': 1, 'department': 1, 'team': 1,
            'schedule': 1, 'calendar': 1, 'agenda': 1, 'presentation': 1,
            
            # Personal/Friend
            'hope': 1, 'thanks': 1, 'thank': 1, 'please': 1, 'regards': 1,
            'sincerely': 1, 'best': 1, 'appreciate': 1, 'kindly': 1,
            
            # Support/Service
            'support': 2, 'help': 1, 'assistance': 1, 'available': 1,
            'question': 1, 'issue': 1, 'resolution': 1, 'service': 1,
            
            # Legitimate transactional
            'order': 3, 'receipt': 3, 'confirmation': 2, 'thank you': 2,
            'appointment': 2, 'reservation': 2, 'booking': 2,
            
            # Communication
            'regarding': 1, 'reference': 1, 'discussion': 1, 'information': 1,
            'details': 1, 'following': 1, 'attached': 1,
        }
        
        # Train with patterns
        self.total_spam_mails = 1000  # Assumed training size
        self.total_ham_mails = 1000
        
        for word, freq in spam_patterns.items():
            self.spam_words[word] = freq
        
        for word, freq in ham_patterns.items():
            self.ham_words[word] = freq
    
    def _tokenize(self, text):
        """Extract words from text"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters but keep words
        words = re.findall(r'\b[a-z]+\b', text)
        
        return words
    
    def _calculate_probability(self, word, is_spam):
        """Calculate P(word|spam) or P(word|ham) using Laplace smoothing"""
        if is_spam:
            # Count: how many times word appears in spam emails
            word_count = self.spam_words.get(word, 0)
            total_words = sum(self.spam_words.values())
        else:
            # Count: how many times word appears in ham emails
            word_count = self.ham_words.get(word, 0)
            total_words = sum(self.ham_words.values())
        
        # Laplace smoothing: add 1 to avoid zero probability
        probability = (word_count + 1) / (total_words + len(self.spam_words) + len(self.ham_words))
        
        return probability
    
    def calculate_spam_score(self, subject, sender, body=""):
        """
        Calculate spam probability using Bayesian theorem.
        Returns: (is_spam, confidence_score, explanation)
        """
        # Combine text for analysis
        text = f"{subject} {sender} {body}".lower()
        words = self._tokenize(text)
        
        if not words:
            return False, 0.0, "No text to analyze"
        
        # Calculate log probabilities to avoid underflow
        # P(spam|words) = P(words|spam) * P(spam) / P(words)
        # Using log: log(P) = log(P(words|spam)) + log(P(spam))
        
        spam_score = math.log(self.total_spam_mails / (self.total_spam_mails + self.total_ham_mails))
        ham_score = math.log(self.total_ham_mails / (self.total_spam_mails + self.total_ham_mails))
        
        # Calculate probability for each word
        detected_spam_words = []
        for word in set(words):  # Use set to count unique words only once
            p_word_spam = self._calculate_probability(word, is_spam=True)
            p_word_ham = self._calculate_probability(word, is_spam=False)
            
            spam_score += math.log(p_word_spam)
            ham_score += math.log(p_word_ham)
            
            # Track which spam words were detected
            if word in self.spam_words and self.spam_words[word] > 5:
                detected_spam_words.append(word)
        
        # Convert log probability to probability
        # Normalize to 0-1 range
        try:
            probability_spam = 1 / (1 + math.exp(ham_score - spam_score))
        except:
            probability_spam = 0.5
        
        # Determine if spam (threshold: 0.5)
        is_spam = probability_spam > 0.5
        
        # Explanation of detection
        explanation = ""
        if detected_spam_words:
            explanation = f"Detected spam indicators: {', '.join(detected_spam_words[:3])}"
        else:
            explanation = "Bayesian analysis based on email patterns"
        
        return is_spam, probability_spam, explanation
    
    def train_on_email(self, subject, sender, body, is_spam):
        """
        Update classifier with new email (for continuous learning).
        Note: In production, you'd persist this to a database.
        """
        text = f"{subject} {sender} {body}"
        words = self._tokenize(text)
        
        if is_spam:
            self.total_spam_mails += 1
            for word in set(words):
                self.spam_words[word] += 1
        else:
            self.total_ham_mails += 1
            for word in set(words):
                self.ham_words[word] += 1


# Global detector instance
_detector = BayesianSpamDetector()


def detect_spam_bayesian(subject, sender, body=""):
    """
    Detect spam using Bayesian classification.
    Returns: (is_spam, confidence_score, explanation)
    
    Industry-standard approach used by Gmail, Outlook, Thunderbird.
    Completely local - no external services.
    """
    is_spam, confidence, explanation = _detector.calculate_spam_score(subject, sender, body)
    
    return is_spam, confidence, explanation


def get_ai_queries():
    """Get predefined cleanup queries"""
    return [
        "unsubscribe",
        "category:promotions older_than:30d",
        "category:social older_than:14d",
        "has:attachment larger:10M older_than:60d"
    ]


def calculate_email_stats(emails_data):
    """Calculate statistics from email list"""
    stats = {
        "total": len(emails_data),
        "by_category": {
            "promotions": 0,
            "social": 0,
            "newsletters": 0,
            "spam": 0,
            "other": 0
        },
        "estimated_storage_mb": 0,
        "oldest_date": None,
        "newest_date": None
    }
    
    for email in emails_data:
        category = email.get("category", "other")
        if category in stats["by_category"]:
            stats["by_category"][category] += 1
        else:
            stats["by_category"]["other"] += 1
        
        # Rough estimate: average email ~50KB
        stats["estimated_storage_mb"] += 0.05
    
    return stats
