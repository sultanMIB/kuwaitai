import re
from typing import Dict, List, Tuple, Optional
from .BaseController import BaseController

class QueryPreprocessor(BaseController):
    def __init__(self):
        super().__init__()
        
        # Greeting patterns in Arabic
        self.greeting_patterns = [
            # Common greetings
            r'^مرحبا$', r'^أهلا$', r'^أهلاً$', r'^هلا$', r'^هلاً$',
            r'^السلام عليكم$', r'^سلام$', r'^صباح الخير$', r'^مساء الخير$',
            r'^ازيك$', r'^إزيك$', r'^كيف حالك$', r'^كيف الحال$',
            r'^شكرا$', r'^شكراً$', r'^مشكور$', r'^مشكورة$',
            r'^عذراً$', r'^عذراً$', r'^عفواً$', r'^عفوا$',
            r'^مع السلامة$', r'^باي$', r'^وداعاً$', r'^وداعا$',
            # With variations
            r'^مرحبا\s*!*$', r'^أهلا\s*!*$', r'^هلا\s*!*$',
            r'^شكرا\s*!*$', r'^شكراً\s*!*$',
        ]
        
        # Compile regex patterns
        self.greeting_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.greeting_patterns]
        
        # Synonym mappings for normalization - ordered from longest to shortest to avoid conflicts
        self.synonym_mappings = {
            # Academic levels - longer phrases first
            'سنة خامسة': 'الفرقة الخامسة',
            'سنة رابعة': 'الفرقة الرابعة',
            'سنة ثالثة': 'الفرقة الثالثة',
            'سنة ثانية': 'الفرقة الثانية',
            'سنة أولى': 'الفرقة الأولى',
            'مستوى خامس': 'الفرقة الخامسة',
            'مستوى رابع': 'الفرقة الرابعة',
            'مستوى ثالث': 'الفرقة الثالثة',
            'مستوى ثاني': 'الفرقة الثانية',
            'مستوى أول': 'الفرقة الأولى',
            'الفرقة التالتة': 'الفرقة الثالثة',
            'الفرقة التانية': 'الفرقة الثانية',
            'الفرقة الاولى': 'الفرقة الأولى',
            
            # Academic terms - longer phrases first
            'تخصص مساند': 'التخصص المساند',
            'تخصص رئيسي': 'التخصص الرئيسي',
            'تخصص فرعي': 'التخصص المساند',
            'تخصص': 'التخصص الرئيسي',
            
            # Common variations - longer phrases first
            'وحدات دراسية': 'وحدات دراسية',  # Keep as is
            'مقررات دراسية': 'وحدات دراسية',
            'مواد دراسية': 'وحدات دراسية',
            'ساعات دراسية': 'وحدات دراسية',
            'وحدات': 'وحدات دراسية',
            'ساعات': 'وحدات دراسية',
            'مقررات': 'وحدات دراسية',
            'مواد': 'وحدات دراسية',
            
            # Question variations
            'ما هو': 'ما هو',
            'ما هي': 'ما هي',
            'إيه': 'ما هو',
            'ايه': 'ما هو',
            'متى': 'متى',
            'كيف': 'كيف',
        }
        
        # Detail request patterns
        self.detail_request_patterns = [
            r'وضح\s+اكتر', r'وضح\s+أكتر', r'وضح\s+اكثر', r'وضح\s+أكثر',
            r'اشرح\s+اكتر', r'اشرح\s+أكتر', r'اشرح\s+اكثر', r'اشرح\s+أكثر',
            r'مثال', r'أمثلة', r'أمثله',
            r'تفاصيل', r'تفاصيل اكتر', r'تفاصيل أكثر',
            r'كيف\s+يعني', r'كيف\s+يقصد', r'يعني\s+ايه', r'يعني\s+إيه',
            r'ممكن\s+توضيح', r'ممكن\s+شرح', r'هل\s+يمكن\s+توضيح',
            r'بالتفصيل', r'تفصيل', r'تفصيلي',
        ]
        
        self.detail_request_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.detail_request_patterns]
        
        # Greeting responses
        self.greeting_responses = [
            "أهلاً وسهلاً! كيف أقدر أساعدك اليوم؟",
            "مرحباً! أنا هنا لمساعدتك في أي سؤال عن النظام الأكاديمي.",
            "أهلاً! كيف يمكنني مساعدتك؟",
            "مرحباً! هل لديك سؤال عن المقررات أو النظام الدراسي؟",
            "أهلاً وسهلاً! كيف أقدر أخدمك؟"
        ]
    
    def is_greeting(self, query: str) -> bool:
        """
        Check if the query is a greeting or small talk
        """
        query = query.strip()
        
        # Check against regex patterns
        for pattern in self.greeting_regex:
            if pattern.match(query):
                return True
        
        # Additional simple checks
        greeting_words = ['مرحبا', 'أهلا', 'هلا', 'سلام', 'شكرا', 'شكراً', 'عذراً', 'عفواً']
        query_words = query.split()
        
        if len(query_words) <= 2:  # Short queries are more likely to be greetings
            for word in query_words:
                if word in greeting_words:
                    return True
        
        return False
    
    def normalize_synonyms(self, query: str) -> str:
        """
        Normalize synonyms in the query to improve retrieval
        """
        normalized_query = query
        
        # Sort mappings by length (longest first) to avoid conflicts
        sorted_mappings = sorted(self.synonym_mappings.items(), key=lambda x: len(x[0]), reverse=True)
        
        # Apply synonym mappings
        for synonym, normalized in sorted_mappings:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(synonym) + r'\b'
            normalized_query = re.sub(pattern, normalized, normalized_query, flags=re.IGNORECASE)
        
        return normalized_query
    
    def is_detail_request(self, query: str) -> bool:
        """
        Check if the user is asking for more details
        """
        query = query.strip()
        
        # Check against regex patterns
        for pattern in self.detail_request_regex:
            if pattern.search(query):
                return True
        
        # Additional simple checks
        detail_words = ['وضح', 'اشرح', 'مثال', 'تفاصيل', 'كيف يعني', 'يعني ايه', 'بالتفصيل']
        query_lower = query.lower()
        
        for word in detail_words:
            if word in query_lower:
                return True
        
        return False
    
    def get_greeting_response(self) -> str:
        """
        Get a random greeting response
        """
        import random
        return random.choice(self.greeting_responses)
    
    def preprocess_query(self, query: str) -> Dict:
        """
        Main preprocessing function that returns processed query info
        """
        original_query = query.strip()
        
        # Check if it's a greeting
        if self.is_greeting(original_query):
            return {
                'is_greeting': True,
                'is_detail_request': False,
                'original_query': original_query,
                'normalized_query': original_query,
                'greeting_response': self.get_greeting_response()
            }
        
        # Check if it's a detail request
        is_detail_request = self.is_detail_request(original_query)
        
        # Normalize synonyms
        normalized_query = self.normalize_synonyms(original_query)
        
        return {
            'is_greeting': False,
            'is_detail_request': is_detail_request,
            'original_query': original_query,
            'normalized_query': normalized_query,
            'greeting_response': None
        }
