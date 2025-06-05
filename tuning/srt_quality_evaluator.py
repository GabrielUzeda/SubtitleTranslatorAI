#!/usr/bin/env python3
"""
SRT Quality Evaluator
Sistema profissional de avaliação de qualidade de legendas SRT traduzidas
Baseado nos critérios ponderados especificados pelo usuário
"""

import re
import os
import json
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
import chardet

@dataclass
class QualityScore:
    """Representa um score de qualidade com justificativa"""
    category: str
    score: float  # 0-10
    weight: float  # Peso percentual
    justification: str
    examples: List[str]
    weighted_score: float

class SRTQualityEvaluator:
    """Avaliador profissional de qualidade de legendas SRT"""
    
    def __init__(self):
        self.weights = {
            "syntax": 0.40,      # 40% - Crítico para rendering
            "fidelity": 0.15,    # 15% - Precisão da tradução
            "fluency": 0.10,     # 10% - Fluência gramatical
            "context": 0.08,     # 8% - Adequação contextual
            "regional": 0.07,    # 7% - Localização regional
            "formality": 0.07,   # 7% - Nível de formalidade
            "gender": 0.07,      # 7% - Marcadores de gênero
            "readability": 0.06  # 6% - Legibilidade
        }
    
    def evaluate_srt_quality(self, original_file: str, translated_file: str, target_lang: str = "pt-br") -> Dict[str, Any]:
        """
        Avalia qualidade completa de um arquivo SRT traduzido
        
        Args:
            original_file: Caminho para arquivo SRT original
            translated_file: Caminho para arquivo SRT traduzido
            target_lang: Idioma alvo ("pt-br" para português brasileiro, "pt" ou "pt-pt" para português de Portugal)
        
        Returns:
            Dicionário com scores detalhados e análise completa
        """
        
        # Carregar arquivos
        original_content = self._load_srt_file(original_file)
        translated_content = self._load_srt_file(translated_file)
        
        if not original_content or not translated_content:
            return {"error": "Não foi possível carregar os arquivos SRT"}
        
        # Parsear blocos SRT
        original_blocks = self._parse_srt_blocks(original_content)
        translated_blocks = self._parse_srt_blocks(translated_content)
        
        # Executar avaliações por categoria
        scores = {}
        
        # 1. Syntax Score (40%)
        scores["syntax"] = self._evaluate_syntax(translated_blocks, translated_content)
        
        # 2. Fidelity Score (15%)
        scores["fidelity"] = self._evaluate_fidelity(original_blocks, translated_blocks)
        
        # 3. Fluency Score (10%)
        scores["fluency"] = self._evaluate_fluency(translated_blocks)
        
        # 4. Context Score (8%)
        scores["context"] = self._evaluate_context(original_blocks, translated_blocks)
        
        # 5. Regional Score (7%)
        scores["regional"] = self._evaluate_regional(translated_blocks, target_lang)
        
        # 6. Formality Score (7%)
        scores["formality"] = self._evaluate_formality(translated_blocks)
        
        # 7. Gender Score (7%)
        scores["gender"] = self._evaluate_gender(translated_blocks)
        
        # 8. Readability Score (6%)
        scores["readability"] = self._evaluate_readability(translated_blocks)
        
        # Calcular score final (já está em escala 0-100 devido aos pesos)
        final_score = sum(scores[cat].weighted_score for cat in scores) * 10  # weighted_score já considera os pesos
        
        return {
            "file_info": {
                "original": original_file,
                "translated": translated_file,
                "target_language": target_lang,
                "original_blocks": len(original_blocks),
                "translated_blocks": len(translated_blocks)
            },
            "category_scores": scores,
            "final_score": final_score,
            "grade": self._get_grade(final_score),
            "summary": self._generate_summary(scores, final_score),
            "recommendations": self._generate_recommendations(scores)
        }
    
    def _load_srt_file(self, filepath: str) -> str:
        """Carrega arquivo SRT com detecção automática de encoding"""
        try:
            # Detectar encoding
            with open(filepath, 'rb') as f:
                raw_data = f.read()
                encoding_info = chardet.detect(raw_data)
                encoding = encoding_info['encoding'] or 'utf-8'
            
            # Carregar com encoding detectado
            with open(filepath, 'r', encoding=encoding) as f:
                return f.read()
        except Exception as e:
            print(f"Erro ao carregar {filepath}: {e}")
            return ""
    
    def _parse_srt_blocks(self, content: str) -> List[Dict]:
        """Parse de blocos SRT para análise estruturada"""
        blocks = []
        srt_blocks = re.split(r'\n\s*\n', content.strip())
        
        for block_text in srt_blocks:
            block_text = block_text.strip()
            if not block_text:
                continue
                
            lines = block_text.split('\n')
            if len(lines) < 2:
                continue
            
            try:
                # Número do bloco
                block_number = int(lines[0].strip())
                
                # Timestamp
                timestamp_line = lines[1].strip()
                timestamp_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', timestamp_line)
                
                if timestamp_match:
                    start_time = timestamp_match.group(1)
                    end_time = timestamp_match.group(2)
                    
                    # Conteúdo (linhas restantes)
                    content_lines = lines[2:] if len(lines) > 2 else []
                    subtitle_content = '\n'.join(content_lines)
                    
                    blocks.append({
                        "number": block_number,
                        "start_time": start_time,
                        "end_time": end_time,
                        "content": subtitle_content,
                        "raw_block": block_text
                    })
            except (ValueError, IndexError):
                continue
        
        return blocks
    
    def _evaluate_syntax(self, blocks: List[Dict], full_content: str) -> QualityScore:
        """Avalia sintaxe SRT (40% do score final)"""
        issues = []
        total_blocks = len(blocks)
        error_count = 0
        
        # Verificar encoding UTF-8
        try:
            full_content.encode('utf-8')
        except UnicodeEncodeError:
            issues.append("Encoding não é UTF-8 válido")
            error_count += 1
        
        # Verificar sequência numérica
        expected_number = 1
        for block in blocks:
            if block["number"] != expected_number:
                issues.append(f"Numeração incorreta: esperado {expected_number}, encontrado {block['number']}")
                error_count += 1
            expected_number += 1
        
        # Verificar formato de timestamp
        timestamp_errors = 0
        for block in blocks:
            timestamp_pattern = r'^\d{2}:\d{2}:\d{2},\d{3}$'
            if not re.match(timestamp_pattern, block["start_time"]) or not re.match(timestamp_pattern, block["end_time"]):
                timestamp_errors += 1
        
        if timestamp_errors > 0:
            issues.append(f"{timestamp_errors} timestamps com formato incorreto")
            error_count += timestamp_errors
        
        # Verificar tags HTML válidas
        html_errors = 0
        for block in blocks:
            content = block["content"]
            # Verificar tags não fechadas
            open_tags = re.findall(r'<(\w+)[^>]*>', content)
            close_tags = re.findall(r'</(\w+)>', content)
            
            for tag in open_tags:
                if open_tags.count(tag) != close_tags.count(tag):
                    html_errors += 1
                    break
        
        if html_errors > 0:
            issues.append(f"{html_errors} blocos com tags HTML malformadas")
            error_count += html_errors
        
        # Verificar espaçamento entre blocos
        spacing_errors = 0
        srt_blocks = re.split(r'\n\s*\n', full_content.strip())
        for i, block in enumerate(srt_blocks[:-1]):
            # Cada bloco deve terminar com duas quebras de linha
            if not block.endswith('\n'):
                spacing_errors += 1
        
        if spacing_errors > 0:
            issues.append(f"{spacing_errors} problemas de espaçamento entre blocos")
        
        # Calcular score (crítico - erros pesam muito)
        if total_blocks == 0:
            score = 0
        else:
            error_ratio = error_count / total_blocks
            score = max(0, 10 - (error_ratio * 15))  # Penalidade pesada para erros sintáticos
        
        justification = f"Analisados {total_blocks} blocos. " + (
            f"Encontrados {len(issues)} tipos de problemas." if issues else "Sintaxe perfeita."
        )
        
        return QualityScore(
            category="Syntax",
            score=score,
            weight=self.weights["syntax"],
            justification=justification,
            examples=issues[:3],  # Mostrar apenas primeiros 3 problemas
            weighted_score=score * self.weights["syntax"]
        )
    
    def _evaluate_fidelity(self, original_blocks: List[Dict], translated_blocks: List[Dict]) -> QualityScore:
        """Avalia fidelidade da tradução (15% do score)"""
        issues = []
        
        # Verificar correspondência de número de blocos
        if len(original_blocks) != len(translated_blocks):
            issues.append(f"Número de blocos difere: {len(original_blocks)} vs {len(translated_blocks)}")
        
        # Verificar preservação de nomes próprios comuns
        proper_names = ["Jean Pierre Polnareff", "Silver Chariot", "Jotaro", "Dio", "Stand"]
        preservation_score = 0
        name_tests = 0
        
        for orig, trans in zip(original_blocks, translated_blocks):
            orig_content = orig["content"].lower()
            trans_content = trans["content"].lower()
            
            for name in proper_names:
                if name.lower() in orig_content:
                    name_tests += 1
                    if name.lower() in trans_content or self._is_valid_translation(name, trans_content):
                        preservation_score += 1
        
        # Verificar omissões ou adições suspeitas
        significant_changes = 0
        for orig, trans in zip(original_blocks, translated_blocks):
            orig_words = len(orig["content"].split())
            trans_words = len(trans["content"].split())
            
            if orig_words > 0:
                ratio = trans_words / orig_words
                if ratio < 0.3 or ratio > 3.0:  # Mudança muito drástica
                    significant_changes += 1
        
        if significant_changes > 0:
            issues.append(f"{significant_changes} blocos com mudanças drásticas de tamanho")
        
        # Calcular score
        if name_tests > 0:
            name_preservation_score = (preservation_score / name_tests) * 10
        else:
            name_preservation_score = 8  # Score padrão se não há nomes para testar
        
        block_count_penalty = 0
        if len(original_blocks) != len(translated_blocks):
            block_count_penalty = 3
        
        change_penalty = (significant_changes / max(len(translated_blocks), 1)) * 5
        
        score = max(0, name_preservation_score - block_count_penalty - change_penalty)
        
        justification = f"Preservação de nomes: {preservation_score}/{name_tests}. " + (
            f"Problemas detectados: {len(issues)}" if issues else "Fidelidade boa."
        )
        
        return QualityScore(
            category="Fidelity",
            score=score,
            weight=self.weights["fidelity"],
            justification=justification,
            examples=issues,
            weighted_score=score * self.weights["fidelity"]
        )
    
    def _evaluate_fluency(self, blocks: List[Dict]) -> QualityScore:
        """Avalia fluência gramatical (10% do score)"""
        issues = []
        
        # Detectar problemas de fluência comuns
        fluency_problems = 0
        total_text_blocks = 0
        
        portuguese_patterns = {
            "article_agreement": r'\b(o|a|os|as)\s+\w+',
            "verb_conjugation": r'\b(é|são|está|estão|foi|foram)\b',
            "pronoun_placement": r'\b(me|te|se|nos|vos)\b'
        }
        
        for block in blocks:
            content = block["content"]
            # Remover tags HTML para análise
            clean_content = re.sub(r'<[^>]+>', '', content)
            
            if len(clean_content.strip()) < 3:
                continue
                
            total_text_blocks += 1
            
            # Detectar possíveis problemas
            # 1. Artigos seguidos por artigos (erro comum)
            if re.search(r'\b(o|a)\s+(o|a)\b', clean_content.lower()):
                fluency_problems += 1
                issues.append(f"Bloco {block['number']}: possível erro de artigo duplo")
            
            # 2. Texto em inglês residual
            english_words = re.findall(r'\b(the|and|you|are|this|that|with|have|will)\b', clean_content.lower())
            if len(english_words) > 2:
                fluency_problems += 1
                issues.append(f"Bloco {block['number']}: possível texto em inglês residual")
            
            # 3. Repetições anômalas
            words = clean_content.lower().split()
            if len(words) > 3:
                repeated = [word for word in set(words) if words.count(word) > 2 and len(word) > 3]
                if repeated:
                    fluency_problems += 1
                    issues.append(f"Bloco {block['number']}: repetição anômala de palavras")
        
        # Calcular score
        if total_text_blocks == 0:
            score = 5  # Score neutro se não há texto para analisar
        else:
            error_ratio = fluency_problems / total_text_blocks
            score = max(0, 10 - (error_ratio * 12))
        
        justification = f"Analisados {total_text_blocks} blocos de texto. Problemas de fluência: {fluency_problems}"
        
        return QualityScore(
            category="Fluency",
            score=score,
            weight=self.weights["fluency"],
            justification=justification,
            examples=issues[:3],
            weighted_score=score * self.weights["fluency"]
        )
    
    def _evaluate_context(self, original_blocks: List[Dict], translated_blocks: List[Dict]) -> QualityScore:
        """Avalia adequação contextual (8% do score)"""
        issues = []
        context_score = 0
        context_tests = 0
        
        # Testes contextuais específicos para anime/ação
        context_patterns = {
            "action_tone": ["batalha", "luta", "ataque", "poder", "força"],
            "respect_levels": ["senhor", "senhora", "você", "tu"],
            "anime_terms": ["jutsu", "técnica", "habilidade", "stand", "carruagem"]
        }
        
        for orig, trans in zip(original_blocks, translated_blocks):
            orig_content = orig["content"].lower()
            trans_content = trans["content"].lower()
            
            # Verificar se tom de ação é mantido
            if any(word in orig_content for word in ["fight", "battle", "attack", "power"]):
                context_tests += 1
                if any(word in trans_content for word in context_patterns["action_tone"]):
                    context_score += 1
                else:
                    issues.append(f"Bloco {orig['number']}: tom de ação pode estar perdido")
            
            # Verificar tradução de expressões idiomáticas
            if "flame" in orig_content and "table" in orig_content and "twelve" in orig_content:
                context_tests += 1
                if "meio dia" in trans_content or "meio-dia" in trans_content:
                    context_score += 2  # Bonus por tradução idiomática correta
                elif "chama" in trans_content and "mesa" in trans_content:
                    issues.append(f"Bloco {orig['number']}: tradução muito literal de expressão idiomática")
        
        # Score baseado em acertos contextuais
        if context_tests > 0:
            score = min(10, (context_score / context_tests) * 10)
        else:
            score = 7  # Score padrão se não há contextos específicos para testar
        
        justification = f"Testes contextuais: {context_score}/{context_tests}. Adequação ao gênero anime/ação."
        
        return QualityScore(
            category="Context",
            score=score,
            weight=self.weights["context"],
            justification=justification,
            examples=issues,
            weighted_score=score * self.weights["context"]
        )
    
    def _evaluate_regional(self, blocks: List[Dict], target_lang: str) -> QualityScore:
        """Avalia localização regional (7% do score) - COM INTELIGÊNCIA DE IDIOMA"""
        issues = []
        brazilian_indicators = 0
        european_indicators = 0
        violations = 0
        total_checks = 0
        
        # Determinar se deve penalizar português europeu ou brasileiro
        expect_brazilian = target_lang.lower() in ["pt-br", "portuguese-br", "brazilian"]
        expect_european = target_lang.lower() in ["pt", "pt-pt", "portuguese", "european"]
        
        # Padrões de português brasileiro
        brazilian_patterns = [
            r'\bvocê\b', r'\bvocês\b',                    # vs "tu/vós"
            r'\bestá\b', r'\bestão\b',                    # vs "estás/estais"  
            r'\bônibus\b',                                # vs "autocarro"
            r'\bxícaras?\b',                              # vs "chávenas"
            r'\bcelular\b',                               # vs "telemóvel"
            r'\bgeladeira\b',                             # vs "frigorífico"
            r'\bbanheiro\b',                              # vs "casa de banho"
            r'\btrem\b',                                  # vs "comboio"
            r'\bmeio cheias?\b',                          # vs "meias"
            r'\bsanduíche\b',                             # vs "sandes"
            r'\bsorvete\b',                               # vs "gelado"
            r'\bcalçada\b',                               # vs "passeio"
            r'\blegal\b',                                 # gíria brasileira
            r'\bmoleque\b', r'\bmoleques\b',              # vs "miúdo"
            r'\bgaroto\b', r'\bgarota\b',                 # vs "rapaz/rapariga"
        ]
        
        # EXPANDIDO: Padrões de português europeu (DEZENAS de palavras)
        european_patterns = [
            # Pronomes e conjugações
            r'\btuas?\b', r'\bvossas?\b',                 # vs "suas"
            r'\bestás\b', r'\bestou\b', r'\bestais\b',    # vs "está/estão"
            r'\btendes\b', r'\bsois\b',                   # arcaísmo europeu
            
            # Vocabulário cotidiano
            r'\bautocarro\b',                             # vs "ônibus"
            r'\btelemóvel\b',                             # vs "celular"
            r'\bfrigorífico\b',                           # vs "geladeira"
            r'\bcasa de banho\b',                         # vs "banheiro"
            r'\bchávenas?\b',                             # vs "xícaras"
            r'\bmeias-chávenas\b',                        # vs "meio cheias"
            r'\bcomboio\b',                               # vs "trem"
            r'\bsandes\b',                                # vs "sanduíche"
            r'\bgelado\b',                                # vs "sorvete"
            r'\bpasseio\b',                               # vs "calçada"
            r'\brapariga\b',                              # vs "garota/menina"
            r'\bmiúdos?\b',                               # vs "garotos/crianças"
            r'\bputos?\b',                                # gíria PT-PT
            r'\bmarretas?\b',                             # gíria PT-PT
            r'\bmacaquinho\b',                            # vs "macacão"
            r'\bdescalços?\b',                            # vs "descalços" (forma BR é igual mas contexto diferente)
            
            # Comida e bebida
            r'\bbicas?\b',                                # vs "cafezinho"
            r'\bgalão\b',                                 # café com leite PT-PT
            r'\bfinos?\b',                                # cerveja pequena
            r'\bimperiais?\b',                            # cerveja (algumas regiões)
            r'\bpastéis de nata\b',                       # vs "pastéis de Belém"
            r'\bbroas?\b',                                # tipo de pão doce
            r'\bfarinheiras?\b',                          # tipo de enchido
            r'\bmorcelas?\b',                             # vs "morcilha"
            
            # Vestuário
            r'\bcamisolas?\b',                            # vs "suéter/blusa"
            r'\bfatos?\b',                                # vs "ternos"
            r'\bcalções\b',                               # vs "shorts"
            r'\btosses?\b',                               # vs "gorros"
            r'\bténis\b',                                 # vs "tênis"
            
            # Casa e objetos
            r'\bestore\b',                                # vs "persiana"
            r'\bligação\b',                               # vs "chamada telefônica"
            r'\bcanalizador\b',                           # vs "encanador"
            r'\belectricista\b',                          # vs "eletricista"
            r'\bcomputador portátil\b',                   # vs "notebook/laptop"
            r'\brato\b',                                  # vs "mouse"
            r'\bteclado\b',                               # igual mas contexto
            r'\becrã\b',                                  # vs "tela"
            r'\bvisor\b',                                 # vs "tela/monitor"
            
            # Verbos e expressões específicas
            r'\balugar\b',                                # vs "alugar" (forma BR)
            r'\bdeitar fora\b',                           # vs "jogar fora"
            r'\bapanhar\b',                               # vs "pegar"
            r'\bata logo\b',                              # expressão PT-PT
            r'\bestou farto\b',                           # vs "estou cheio"
            r'\bque caca\b',                              # expressão PT-PT
            r'\bque chatice\b',                           # vs "que chato"
            r'\bestou tramado\b',                         # gíria PT-PT
            r'\bestás à vontade\b',                       # vs "fique à vontade"
            
            # Expressões temporais e quantidades
            r'\bpara o ano\b',                            # vs "ano que vem"
            r'\bganda\b',                                 # gíria: "muito grande"
            r'\bfixe\b',                                  # vs "legal/maneiro"
            r'\bporreiro\b',                              # vs "legal/bacana"
            r'\bbué\b',                                   # vs "muito"
            
            # Dinheiro e compras
            r'\bcêntimos\b',                              # vs "centavos"
            r'\bhipermercado\b',                          # vs "hipermercado" (igual mas contexto)
            r'\btabacaria\b',                             # vs "tabacaria"
            r'\bestanco\b',                               # banca de jornais
            
            # Trânsito e transporte
            r'\bmatrícula\b',                             # vs "placa"
            r'\bparque de estacionamento\b',              # vs "estacionamento"
            r'\bsinal\b',                                 # vs "semáforo"
            r'\bpassadeira\b',                            # vs "faixa de pedestres"
            r'\brotunda\b',                               # vs "rotatória"
            r'\bautoestrada\b',                           # vs "rodovia/autoestrada"
            
            # Educação
            r'\bfaculdade\b',                             # contexto diferente
            r'\bliceu\b',                                 # vs "colégio"
            r'\bprimária\b',                              # vs "fundamental"
            
            # NOVO: Detectar gagueira não traduzida (problema específico)
            r'\bH-Hold\b', r'\bW-What\b', r'\bN-No\b', r'\bS-Stop\b', r'\bB-But\b'
        ]
        
        for block in blocks:
            content = block["content"].lower()
            clean_content = re.sub(r'<[^>]+>', '', content)
            
            if len(clean_content.strip()) < 3:
                continue
            
            # Contar indicadores brasileiros
            for pattern in brazilian_patterns:
                if re.search(pattern, clean_content):
                    brazilian_indicators += 1
                    total_checks += 1
            
            # Contar indicadores europeus
            for pattern in european_patterns:
                if re.search(pattern, clean_content):
                    european_indicators += 1
                    total_checks += 1
        
        # LÓGICA INTELIGENTE: só penalizar se não bater com o idioma alvo
        if expect_brazilian:
            # Se esperamos português brasileiro, penalizar português europeu
            violations = european_indicators
            for block in blocks:
                content = block["content"].lower()
                clean_content = re.sub(r'<[^>]+>', '', content)
                for pattern in european_patterns:
                    if re.search(pattern, clean_content):
                        if "chávenas" in pattern:
                            issues.append(f"Bloco {block['number']}: ERRO CRÍTICO - 'chávenas' (português de Portugal, esperado: pt-br)")
                        elif any(stutter in pattern for stutter in ["H-Hold", "W-What", "N-No", "S-Stop", "B-But"]):
                            issues.append(f"Bloco {block['number']}: ERRO - gagueira não traduzida: {pattern}")
                        else:
                            issues.append(f"Bloco {block['number']}: português europeu detectado (esperado: pt-br): {pattern}")
                        break  # Um erro por bloco
        
        elif expect_european:
            # Se esperamos português europeu, penalizar português brasileiro
            violations = brazilian_indicators
            for block in blocks:
                content = block["content"].lower()
                clean_content = re.sub(r'<[^>]+>', '', content)
                for pattern in brazilian_patterns:
                    if re.search(pattern, clean_content):
                        issues.append(f"Bloco {block['number']}: português brasileiro detectado (esperado: pt-pt): {pattern}")
                        break  # Um erro por bloco
        
        else:
            # Idioma não especificado ou genérico - não penalizar nenhum
            violations = 0
            issues.append("Idioma alvo não específico - avaliação regional neutra")
        
        # Calcular score baseado nas violações
        if total_checks == 0:
            score = 8  # Score padrão se não há indicadores regionais
        else:
            violation_ratio = violations / total_checks
            score = max(0, 10 - (violation_ratio * 12))  # Penalidade moderada mas firme
        
        # Bonus por usar o dialeto correto
        if expect_brazilian and brazilian_indicators > european_indicators:
            score = min(10, score + 1)
        elif expect_european and european_indicators > brazilian_indicators:
            score = min(10, score + 1)
        
        # Penalidade extra para violações críticas
        critical_violations = len([issue for issue in issues if "CRÍTICO" in issue])
        if critical_violations > 0:
            score = max(0, score - (critical_violations * 2))
        
        # Determinar justificativa baseada no idioma alvo
        if expect_brazilian:
            justification = f"Alvo: pt-br | Brasileiro: {brazilian_indicators}, Europeu (violações): {european_indicators}"
        elif expect_european:
            justification = f"Alvo: pt-pt | Europeu: {european_indicators}, Brasileiro (violações): {brazilian_indicators}"
        else:
            justification = f"Alvo: genérico | Brasileiro: {brazilian_indicators}, Europeu: {european_indicators}"
        
        return QualityScore(
            category="Regional",
            score=score,
            weight=self.weights["regional"],
            justification=justification,
            examples=issues[:5],  # Mostrar até 5 exemplos
            weighted_score=score * self.weights["regional"]
        )
    
    def _evaluate_formality(self, blocks: List[Dict]) -> QualityScore:
        """Avalia nível de formalidade (7% do score)"""
        issues = []
        
        # Detectar inconsistências de formalidade
        formal_indicators = 0
        informal_indicators = 0
        
        formal_patterns = [r'\bsenhor\b', r'\bsenhora\b', r'\bvossa\b']
        informal_patterns = [r'\bvocê\b', r'\bcara\b', r'\bmano\b']
        
        for block in blocks:
            content = block["content"].lower()
            clean_content = re.sub(r'<[^>]+>', '', content)
            
            for pattern in formal_patterns:
                formal_indicators += len(re.findall(pattern, clean_content))
            
            for pattern in informal_patterns:
                informal_indicators += len(re.findall(pattern, clean_content))
        
        total_indicators = formal_indicators + informal_indicators
        
        if total_indicators == 0:
            score = 8  # Score neutro se não há indicadores
        elif formal_indicators == 0 or informal_indicators == 0:
            score = 10  # Consistente em uma direção
        else:
            # Penalizar mistura excessiva
            consistency = abs(formal_indicators - informal_indicators) / total_indicators
            score = 5 + (consistency * 5)
        
        # Para anime, informalidade é geralmente apropriada
        if informal_indicators > formal_indicators:
            score = min(10, score + 1)
        
        justification = f"Formal: {formal_indicators}, Informal: {informal_indicators}. Consistência avaliada."
        
        return QualityScore(
            category="Formality",
            score=score,
            weight=self.weights["formality"],
            justification=justification,
            examples=issues,
            weighted_score=score * self.weights["formality"]
        )
    
    def _evaluate_gender(self, blocks: List[Dict]) -> QualityScore:
        """Avalia marcadores de gênero (7% do score)"""
        issues = []
        
        # Verificar concordância de gênero básica
        gender_errors = 0
        total_gender_checks = 0
        
        # Padrões problemáticos comuns
        problematic_patterns = [
            r'\bo\s+\w+a\b',  # "o mesa" (artigo masculino + substantivo feminino)
            r'\ba\s+\w+o\b',  # "a carro" (artigo feminino + substantivo masculino)
        ]
        
        for block in blocks:
            content = block["content"].lower()
            clean_content = re.sub(r'<[^>]+>', '', content)
            
            for pattern in problematic_patterns:
                matches = re.findall(pattern, clean_content)
                if matches:
                    gender_errors += len(matches)
                    total_gender_checks += len(matches)
                    issues.append(f"Bloco {block['number']}: possível erro de concordância de gênero")
        
        # Para este contexto, se não há erros evidentes, assume-se que está correto
        if total_gender_checks == 0:
            score = 9  # Score alto por padrão se não há problemas detectados
        else:
            error_ratio = gender_errors / total_gender_checks
            score = max(0, 10 - (error_ratio * 15))
        
        justification = f"Verificações de gênero: {gender_errors} erros em {total_gender_checks} casos analisados"
        
        return QualityScore(
            category="Gender",
            score=score,
            weight=self.weights["gender"],
            justification=justification,
            examples=issues[:2],
            weighted_score=score * self.weights["gender"]
        )
    
    def _evaluate_readability(self, blocks: List[Dict]) -> QualityScore:
        """Avalia legibilidade (6% do score)"""
        issues = []
        
        line_length_violations = 0
        line_count_violations = 0
        total_blocks = 0
        
        for block in blocks:
            content = block["content"]
            clean_content = re.sub(r'<[^>]+>', '', content)  # Remove HTML
            
            if len(clean_content.strip()) < 2:
                continue
                
            total_blocks += 1
            lines = clean_content.split('\n')
            
            # Verificar número de linhas por bloco (≤3)
            if len(lines) > 3:
                line_count_violations += 1
                issues.append(f"Bloco {block['number']}: {len(lines)} linhas (máximo recomendado: 3)")
            
            # Verificar caracteres por linha (≤40)
            for i, line in enumerate(lines):
                if len(line.strip()) > 40:
                    line_length_violations += 1
                    if len(issues) < 5:  # Limitar exemplos
                        issues.append(f"Bloco {block['number']}, linha {i+1}: {len(line)} caracteres (máximo: 40)")
        
        # Calcular score
        if total_blocks == 0:
            score = 5
        else:
            length_penalty = (line_length_violations / total_blocks) * 5
            count_penalty = (line_count_violations / total_blocks) * 3
            score = max(0, 10 - length_penalty - count_penalty)
        
        justification = f"Blocos analisados: {total_blocks}. Violações de comprimento: {line_length_violations}, linhas: {line_count_violations}"
        
        return QualityScore(
            category="Readability",
            score=score,
            weight=self.weights["readability"],
            justification=justification,
            examples=issues[:3],
            weighted_score=score * self.weights["readability"]
        )
    
    def _is_valid_translation(self, original_name: str, translated_content: str) -> bool:
        """Verifica se nome foi traduzido adequadamente"""
        translations = {
            "silver chariot": ["carruagem de prata", "silver chariot"],
            "jean pierre polnareff": ["jean pierre polnareff", "polnareff"],
            "stand": ["stand", "alma"]
        }
        
        original_lower = original_name.lower()
        if original_lower in translations:
            return any(trans in translated_content.lower() for trans in translations[original_lower])
        
        return False
    
    def _get_grade(self, score: float) -> str:
        """Converte score numérico em nota qualitativa"""
        if score >= 90:
            return "A+ (Excelente)"
        elif score >= 80:
            return "A (Muito Bom)"
        elif score >= 70:
            return "B (Bom)"
        elif score >= 60:
            return "C (Regular)"
        elif score >= 50:
            return "D (Ruim)"
        else:
            return "F (Falha)"
    
    def _generate_summary(self, scores: Dict[str, QualityScore], final_score: float) -> str:
        """Gera resumo executivo da avaliação"""
        strongest = max(scores.values(), key=lambda x: x.score)
        weakest = min(scores.values(), key=lambda x: x.score)
        
        return f"""
        Score Final: {final_score:.1f}/100 ({self._get_grade(final_score)})
        
        Ponto Forte: {strongest.category} ({strongest.score:.1f}/10)
        Ponto Fraco: {weakest.category} ({weakest.score:.1f}/10)
        
        A tradução {'atende aos padrões profissionais' if final_score >= 70 else 'precisa de melhorias'}.
        """
    
    def _generate_recommendations(self, scores: Dict[str, QualityScore]) -> List[str]:
        """Gera recomendações baseadas nos scores"""
        recommendations = []
        
        for category, score_obj in scores.items():
            if score_obj.score < 7:
                if category == "syntax":
                    recommendations.append("🔧 Corrigir problemas de sintaxe SRT - PRIORIDADE ALTA")
                elif category == "fidelity":
                    recommendations.append("📝 Revisar fidelidade da tradução")
                elif category == "fluency":
                    recommendations.append("✏️ Melhorar fluência e gramática")
                elif category == "context":
                    recommendations.append("🎭 Ajustar adequação contextual")
                elif category == "readability":
                    recommendations.append("👁️ Otimizar legibilidade das legendas")
        
        if not recommendations:
            recommendations.append("✅ Tradução de alta qualidade - manter padrão atual")
        
        return recommendations

def main():
    """Função principal para teste do avaliador"""
    evaluator = SRTQualityEvaluator()
    
    # Exemplo de uso
    original_file = "../example/example.eng.srt"
    translated_file = "../example/example.pt-br.srt"
    
    if os.path.exists(original_file) and os.path.exists(translated_file):
        # NOVO: passando target_lang baseado no nome do arquivo traduzido
        target_lang = "pt-br"  # Default para português brasileiro
        if "pt-pt" in translated_file.lower() or ".pt." in translated_file.lower():
            target_lang = "pt-pt"
        
        result = evaluator.evaluate_srt_quality(original_file, translated_file, target_lang)
        
        print("🏆 AVALIAÇÃO DE QUALIDADE SRT")
        print("=" * 60)
        print(f"Arquivo Original: {result['file_info']['original']}")
        print(f"Arquivo Traduzido: {result['file_info']['translated']}")
        print(f"Idioma Alvo: {result['file_info']['target_language']}")
        print(f"Score Final: {result['final_score']:.1f}/100 ({result['grade']})")
        print()
        
        print("📊 SCORES POR CATEGORIA:")
        for category, score_obj in result['category_scores'].items():
            print(f"{score_obj.category}: {score_obj.score:.1f}/10 (peso: {score_obj.weight*100:.0f}%)")
            print(f"   {score_obj.justification}")
            if score_obj.examples:
                print(f"   Exemplos: {'; '.join(score_obj.examples[:2])}")
            print()
        
        print("💡 RECOMENDAÇÕES:")
        for rec in result['recommendations']:
            print(f"   {rec}")
        
        # Salvar relatório
        timestamp = int(time.time())
        report_file = f"quality_report_{timestamp}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n💾 Relatório salvo em: {report_file}")
    
    else:
        print("❌ Arquivos de exemplo não encontrados")

if __name__ == "__main__":
    import time
    main() 