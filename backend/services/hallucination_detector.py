from typing import Dict, List
import re

class HallucinationDetector:
    """
    Detect and filter entities that LLM may have hallucinated
    
    Catches:
    - Entities with elaborate names not in source text
    - Over-detailed descriptions beyond source material
    - Invented relationships not mentioned
    """
    
    def __init__(self):
        self.suspicious_patterns = [
            # Overly elaborate titles
            r'\bthe (great|mighty|terrible|magnificent|dread)\b',
            # Multiple titles (King Lord Duke...)
            r'\b(king|queen|lord|duke|baron)\s+\w+\s+(the|of)\b',
            # Very long names (5+ words)
            r'^\w+(\s+\w+){4,}$',
        ]
    
    def check_entity(self, entity: Dict, source_text: str) -> Dict:
        """
        Check if entity might be hallucinated
        
        Returns entity with hallucination_risk score (0-1)
        """
        risk_score = 0.0
        reasons = []
        
        name = entity.get('name', '')
        description = entity.get('description', '')
        
        # Check 1: Name appears in source
        if not self._name_in_source(name, source_text):
            risk_score += 0.5
            reasons.append("Name not found in source text")
        
        # Check 2: Suspicious patterns
        for pattern in self.suspicious_patterns:
            if re.search(pattern, name.lower()):
                risk_score += 0.3
                reasons.append(f"Suspicious pattern in name: {pattern}")
        
        # Check 3: Description much longer than source mentions
        source_lower = source_text.lower()
        name_lower = name.lower()
        
        # Find all mentions of this entity
        mentions = source_lower.count(name_lower)
        
        if mentions == 0:
            risk_score += 0.4
            reasons.append("Entity name never mentioned")
        elif mentions == 1 and len(description) > 200:
            risk_score += 0.2
            reasons.append("Very detailed despite single mention")
        
        # Check 4: Confidence vs detail mismatch
        confidence = entity.get('confidence', 0.5)
        detail_level = len(description)
        
        if confidence > 0.9 and detail_level > 300:
            # High confidence with extensive detail is suspicious
            # (Unless multiple mentions)
            if mentions < 3:
                risk_score += 0.2
                reasons.append("Suspiciously detailed for mentions count")
        
        # Add hallucination metadata
        entity['hallucination_risk'] = min(1.0, risk_score)
        entity['hallucination_reasons'] = reasons
        
        # Lower confidence if high risk
        if risk_score > 0.5:
            entity['confidence'] = min(
                entity.get('confidence', 0.5),
                0.6  # Cap at medium-low confidence
            )
            entity['flagged'] = True
            entity['flag_reason'] = f"Possible hallucination: {', '.join(reasons)}"
        
        return entity
    
    def _name_in_source(self, name: str, source: str) -> bool:
        """Check if name (or parts of it) appear in source"""
        name_lower = name.lower()
        source_lower = source.lower()
        
        # Exact match
        if name_lower in source_lower:
            return True
        
        # Check each word of the name
        words = name_lower.split()
        significant_words = [w for w in words if len(w) > 3]
        
        if not significant_words:
            return False
        
        # At least half the significant words should appear
        found = sum(1 for word in significant_words if word in source_lower)
        
        return found >= len(significant_words) / 2
    
    def filter_hallucinations(
        self,
        entities: Dict,
        source_text: str,
        threshold: float = 0.7
    ) -> Dict:
        """
        Filter out likely hallucinated entities
        
        Args:
            entities: Extracted entities
            source_text: Original chat text
            threshold: Hallucination risk above this = remove
        
        Returns:
            Filtered entities
        """
        filtered = {}
        
        for entity_type, entity_list in entities.items():
            filtered[entity_type] = []
            
            for entity in entity_list:
                checked = self.check_entity(entity, source_text)
                
                # Only keep if below hallucination threshold
                if checked.get('hallucination_risk', 0) < threshold:
                    filtered[entity_type].append(checked)
        
        return filtered


# Usage in entity extractor:
# detector = HallucinationDetector()
# entities = detector.filter_hallucinations(raw_entities, source_text)
