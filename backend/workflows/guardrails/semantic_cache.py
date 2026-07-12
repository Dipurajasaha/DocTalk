import logging
from typing import Literal
from backend.core.database import prisma

logger = logging.getLogger(__name__)

class TrieNode:
    def __init__(self):
        self.children: dict[str, 'TrieNode'] = {}
        self.is_end_of_word: bool = False

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str) -> None:
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end_of_word = True

    def search(self, word: str) -> bool:
        """Returns True if the exact word is in the Trie."""
        node = self.root
        for char in word:
            if char not in node.children:
                return False
            node = node.children[char]
        return node.is_end_of_word

    def search_prefix(self, word: str) -> bool:
        """Returns True if the word starts with any prefix in the Trie."""
        node = self.root
        for char in word:
            if char not in node.children:
                return False
            node = node.children[char]
            if node.is_end_of_word:
                return True
        return False

class SemanticCacheManager:
    def __init__(self):
        self.allowed_trie = Trie()
        self.blocked_trie = Trie()
        self.is_loaded = False

    async def _load_from_db(self):
        if self.is_loaded:
            return
            
        try:
            words = await prisma.semanticcacheword.find_many()
            
            if not words:
                await self._seed_initial()
                words = await prisma.semanticcacheword.find_many()
                
            for w in words:
                word_str = w.word.lower()
                if w.category == "ALLOWED":
                    self.allowed_trie.insert(word_str)
                elif w.category == "BLOCKED":
                    self.blocked_trie.insert(word_str)
            self.is_loaded = True
            logger.info(f"Loaded {len(words)} words into Semantic Cache.")
        except Exception as e:
            logger.error(f"Failed to load semantic cache from DB: {e}")

    async def _seed_initial(self):
        """Seed the cache with obvious defaults so it's not starting totally blank."""
        initial_allowed = [
            "medical", "health", "disease", "symptom", "medicine", "treatment", 
            "prescription", "fever", "cough", "headache", "blood", "report", 
            "doctor", "hospital", "clinic", "hello", "hi", "thanks", "appointment"
        ]
        initial_blocked = [
            "python", "script", "java", "code", "bomb", "bypass", "jailbreak",
            "dan", "hack", "hacking", "program", "translate", "summarize",
            "ignore", "disregard"
        ]
        
        logger.info("Seeding initial Semantic Cache...")
        for w in initial_allowed:
            await prisma.semanticcacheword.create(data={"word": w, "category": "ALLOWED"})
        for w in initial_blocked:
            await prisma.semanticcacheword.create(data={"word": w, "category": "BLOCKED"})

    async def check_tokens(self, tokens: list[str]) -> Literal["ALLOWED", "BLOCKED", "UNKNOWN"]:
        await self._load_from_db()
        
        # 1. Check if ANY token triggers the blocked trie (prefix match is safer for blocks)
        for token in tokens:
            if self.blocked_trie.search_prefix(token):
                logger.info(f"[Cache] Hit [BLOCKED]: Token '{token}'")
                return "BLOCKED"
                
        # 2. Check if ANY core token is in the allowed trie
        has_allowed = False
        matched_token = None
        for token in tokens:
            if self.allowed_trie.search(token):
                has_allowed = True
                matched_token = token
                break
                
        if has_allowed:
            logger.info(f"[Cache] Hit [ALLOWED]: Token '{matched_token}'")
            return "ALLOWED"
            
        logger.info(f"[Cache] MISS: No tokens found in either Trie.")
        return "UNKNOWN"

    async def add_allowed(self, word: str):
        word = word.lower().strip()
        if not word: return
        self.allowed_trie.insert(word)
        try:
            existing = await prisma.semanticcacheword.find_first(where={"word": word})
            if not existing:
                await prisma.semanticcacheword.create(data={"word": word, "category": "ALLOWED"})
        except Exception as e:
            logger.error(f"Failed to save allowed word '{word}' to DB: {e}")

    async def add_blocked(self, word: str):
        word = word.lower().strip()
        if not word: return
        self.blocked_trie.insert(word)
        try:
            existing = await prisma.semanticcacheword.find_first(where={"word": word})
            if not existing:
                await prisma.semanticcacheword.create(data={"word": word, "category": "BLOCKED"})
        except Exception as e:
            logger.error(f"Failed to save blocked word '{word}' to DB: {e}")

# Global singleton
cache_manager = SemanticCacheManager()
