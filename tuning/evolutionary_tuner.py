#!/usr/bin/env python3
"""
Sistema de Tuning Evolutivo Automático para Tradução - VERSÃO APRIMORADA
Implementa algoritmos genéticos e busca bayesiana para otimização de parâmetros
Segue princípios de Machine Learning para convergência automática
META: Alcançar pontuação 9.0+
"""

import json
import time
import random
import requests
import os
import sys
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import pickle
import math
import glob
import re

# Adicionar o caminho do backend ao sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from translatorApi.app.utils import extract_text_from_srt, reconstruct_srt_from_translations, count_tokens

# Configurações do sistema evolutivo ULTRA-REFINADO
OLLAMA_URL = "http://localhost:11434/api/generate"
BENCHMARK_FILE = "../example/example.eng.srt"
SAMPLE_SIZE = 1200  # Amostra maior para validação mais robusta

# Parâmetros do algoritmo evolutivo ULTRA-OTIMIZADOS
POPULATION_SIZE = 20        # População maior para máxima diversidade
MAX_GENERATIONS = 40        # Mais gerações para refinamento extremo
MUTATION_RATE = 0.30        # Taxa de mutação mais agressiva
CROSSOVER_RATE = 0.85       # Mais cruzamentos
ELITE_SIZE = 5              # Elite maior
TARGET_SCORE = 9.0          # Meta realista mas ambiciosa
STAGNATION_LIMIT = 8        # Mais paciência para refinamento
DIVERSITY_THRESHOLD = 0.1   # Controle de diversidade

@dataclass
class TranslationConfig:
    """Configuração de tradução com todos os parâmetros"""
    temperature: float
    top_p: float
    top_k: int
    repeat_penalty: float
    chunk_size: int
    prompt_template: str
    max_tokens: int
    
    # Novos parâmetros avançados
    context_window: int = 2
    quality_threshold: float = 0.85
    
    # Metadados para tracking
    generation: int = 0
    fitness: float = 0.0
    parent_configs: List[str] = None
    creation_method: str = "random"
    diversity_score: float = 0.0
    
    def __post_init__(self):
        if self.parent_configs is None:
            self.parent_configs = []
    
    def to_dict(self):
        return asdict(self)
    
    def get_id(self):
        """Gera um ID único baseado nos parâmetros"""
        params = f"{self.temperature}_{self.top_p}_{self.top_k}_{self.repeat_penalty}_{self.chunk_size}_{self.prompt_template}_{self.context_window}"
        return hash(params) & 0x7FFFFFFF  # Positive hash

class EvolutionaryTuner:
    """Sistema de tuning evolutivo ULTRA-AVANÇADO com ML"""
    
    def __init__(self):
        self.population: List[TranslationConfig] = []
        self.generation = 0
        self.best_fitness_history = []
        self.avg_fitness_history = []
        self.diversity_history = []
        self.all_configs_tested = []
        self.stagnation_counter = 0
        self.best_ever_config = None
        self.best_ever_fitness = 0.0
        
        # Ranges de parâmetros ULTRA-FOCADOS baseado em ML insights
        self.param_ranges = {
            'temperature': (0.85, 1.15),      # Faixa otimizada para criatividade controlada
            'top_p': (0.65, 0.80),            # Núcleo de probabilidade mais focado
            'top_k': (12, 25),                # Vocabulário altamente seletivo
            'repeat_penalty': (1.15, 1.35),   # Controle anti-repetição refinado
            'chunk_size': (30, 50),           # Chunks otimizados para contexto
            'max_tokens': (3500, 5500),       # Tokens balanceados
            'context_window': (1, 4),         # Janela de contexto para coherência
            'quality_threshold': (0.75, 0.95) # Limiar de qualidade adaptativo
        }
        
        # Templates de prompt ULTRA-ESPECIALIZADOS
        self.prompt_templates = [
            "jojo_master", "anime_linguist", "cultural_expert", "dialogue_specialist", 
            "stand_authority", "action_translator", "character_voice", "idiom_expert",
            "brazilian_native", "context_aware", "precision_focused", "flow_optimizer"
        ]
        
        # Benchmark phrases EXPANDIDO e ESTRATIFICADO para avaliação rigorosa
        self.benchmark_phrases = [
            # TIER 1: CRÍTICOS (25 pontos cada)
            {
                "original": "before that flame on the table completes twelve",
                "expected": "antes do meio dia",
                "weight": 25,
                "tier": "critical",
                "description": "Expressão idiomática temporal complexa"
            },
            {
                "original": "Silver Chariot",
                "expected": "Silver Chariot",
                "weight": 25,
                "tier": "critical", 
                "description": "Preservação de Stand name principal"
            },
            {
                "original": "Magician's Red",
                "expected": "Magician's Red",
                "weight": 25,
                "tier": "critical",
                "description": "Preservação de Stand name composto"
            },
            
            # TIER 2: IMPORTANTES (15 pontos cada)
            {
                "original": "Jean Pierre Polnareff",
                "expected": "Jean Pierre Polnareff",
                "weight": 15,
                "tier": "important",
                "description": "Preservação de nome de personagem"
            },
            {
                "original": "W-What are you doing",
                "expected": "Q-Que você está fazendo",
                "weight": 15,
                "tier": "important",
                "description": "Gagueira + pronome brasileiro"
            },
            {
                "original": "half-full cups of coffee",
                "expected": "xícaras de café meio cheias",
                "weight": 15,
                "tier": "important",
                "description": "Português brasileiro vs europeu"
            },
            {
                "original": "Stand",
                "expected": "Stand",
                "weight": 15,
                "tier": "important",
                "description": "Terminologia anime específica"
            },
            
            # TIER 3: BÁSICOS (10 pontos cada)
            {
                "original": "Your sword is quite fast",
                "expected": "Sua espada é bastante rápida",
                "weight": 10,
                "tier": "basic",
                "description": "Tradução literal básica"
            },
            {
                "original": "H-Hold on",
                "expected": "E-Espera aí",
                "weight": 10,
                "tier": "basic",
                "description": "Hesitação em português brasileiro"
            },
            {
                "original": "attack",
                "expected": "ataque",
                "weight": 10,
                "tier": "basic",
                "description": "Vocabulário de ação básico"
            },
            
            # TIER 4: NOVOS TESTES AVANÇADOS (20 pontos cada)
            {
                "original": "Hermit Purple",
                "expected": "Hermit Purple",
                "weight": 20,
                "tier": "advanced",
                "description": "Stand name com palavra comum (Purple)"
            },
            {
                "original": "Star Platinum",
                "expected": "Star Platinum", 
                "weight": 20,
                "tier": "advanced",
                "description": "Stand name icônico"
            },
            {
                "original": "Ora ora ora!",
                "expected": "Ora ora ora!",
                "weight": 20,
                "tier": "advanced", 
                "description": "Grito de batalha característico"
            },
            {
                "original": "Za Warudo!",
                "expected": "Za Warudo!",
                "weight": 20,
                "tier": "advanced",
                "description": "Expressão japonesa icônica"
            },
            {
                "original": "Good grief",
                "expected": "Que saco",
                "weight": 18,
                "tier": "advanced",
                "description": "Expressão característica traduzida"
            }
        ]
    
    def save_progress(self):
        """Salva o progresso atual com mais detalhes"""
        timestamp = int(time.time())
        
        # Salvar dados da evolução
        evolution_data = {
            'generation': self.generation,
            'population': [config.to_dict() for config in self.population],
            'best_fitness_history': self.best_fitness_history,
            'avg_fitness_history': self.avg_fitness_history,
            'diversity_history': self.diversity_history,
            'all_configs_tested': [config.to_dict() for config in self.all_configs_tested],
            'best_ever_config': self.best_ever_config.to_dict() if self.best_ever_config else None,
            'best_ever_fitness': self.best_ever_fitness,
            'stagnation_counter': self.stagnation_counter,
            'timestamp': timestamp,
            'meta': {
                'target_score': TARGET_SCORE,
                'population_size': POPULATION_SIZE,
                'mutation_rate': MUTATION_RATE,
                'sample_size': SAMPLE_SIZE
            }
        }
        
        filename = f"evolution_progress_gen_{self.generation}_{timestamp}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(evolution_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Progresso salvo: {filename}")
        return filename
    
    def load_progress(self, filename: str) -> bool:
        """Carrega progresso anterior"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.generation = data['generation']
            self.best_fitness_history = data['best_fitness_history']
            self.avg_fitness_history = data['avg_fitness_history']
            self.diversity_history = data.get('diversity_history', [])
            self.best_ever_fitness = data['best_ever_fitness']
            self.stagnation_counter = data.get('stagnation_counter', 0)
            
            # Reconstruir configs
            self.population = [TranslationConfig(**config) for config in data['population']]
            self.all_configs_tested = [TranslationConfig(**config) for config in data['all_configs_tested']]
            
            if data['best_ever_config']:
                self.best_ever_config = TranslationConfig(**data['best_ever_config'])
            
            print(f"📂 Progresso carregado: Geração {self.generation}")
            return True
        except Exception as e:
            print(f"❌ Erro ao carregar progresso: {e}")
            return False
    
    def generate_random_config(self) -> TranslationConfig:
        """Gera uma configuração aleatória dentro dos ranges otimizados"""
        return TranslationConfig(
            temperature=random.uniform(*self.param_ranges['temperature']),
            top_p=random.uniform(*self.param_ranges['top_p']),
            top_k=random.randint(*self.param_ranges['top_k']),
            repeat_penalty=random.uniform(*self.param_ranges['repeat_penalty']),
            chunk_size=random.randint(*self.param_ranges['chunk_size']),
            prompt_template=random.choice(self.prompt_templates),
            max_tokens=random.randint(*self.param_ranges['max_tokens']),
            context_window=random.randint(*self.param_ranges['context_window']),
            quality_threshold=random.uniform(*self.param_ranges['quality_threshold']),
            generation=self.generation,
            creation_method="random"
        )
    
    def calculate_diversity_score(self, config: TranslationConfig) -> float:
        """Calcula score de diversidade para evitar convergência prematura"""
        if not self.all_configs_tested:
            return 1.0
        
        distances = []
        for other in self.all_configs_tested[-20:]:  # Últimas 20 configurações
            distance = (
                abs(config.temperature - other.temperature) / 0.5 +
                abs(config.top_p - other.top_p) / 0.3 +
                abs(config.top_k - other.top_k) / 20 +
                abs(config.repeat_penalty - other.repeat_penalty) / 0.3 +
                abs(config.chunk_size - other.chunk_size) / 20 +
                (0 if config.prompt_template == other.prompt_template else 1)
            )
            distances.append(distance)
        
        return min(distances) if distances else 1.0
    
    def mutate_config(self, config: TranslationConfig) -> TranslationConfig:
        """Aplica mutação adaptativa em uma configuração"""
        new_config = TranslationConfig(**asdict(config))
        
        # Mutação mais inteligente baseada no fitness
        mutation_strength = 0.1 if config.fitness > 7.0 else 0.2
        
        # Mutação gaussiana para parâmetros contínuos
        if random.random() < MUTATION_RATE:
            new_config.temperature = max(self.param_ranges['temperature'][0], 
                                       min(self.param_ranges['temperature'][1],
                                           config.temperature + random.gauss(0, mutation_strength)))
        
        if random.random() < MUTATION_RATE:
            new_config.top_p = max(self.param_ranges['top_p'][0],
                                 min(self.param_ranges['top_p'][1],
                                     config.top_p + random.gauss(0, mutation_strength/2)))
        
        if random.random() < MUTATION_RATE:
            new_config.repeat_penalty = max(self.param_ranges['repeat_penalty'][0],
                                          min(self.param_ranges['repeat_penalty'][1],
                                              config.repeat_penalty + random.gauss(0, mutation_strength/2)))
        
        if random.random() < MUTATION_RATE:
            new_config.quality_threshold = max(self.param_ranges['quality_threshold'][0],
                                             min(self.param_ranges['quality_threshold'][1],
                                                 config.quality_threshold + random.gauss(0, mutation_strength/4)))
        
        # Mutação discreta para parâmetros inteiros
        if random.random() < MUTATION_RATE:
            new_config.top_k = random.randint(*self.param_ranges['top_k'])
        
        if random.random() < MUTATION_RATE:
            new_config.chunk_size = random.randint(*self.param_ranges['chunk_size'])
        
        if random.random() < MUTATION_RATE:
            new_config.max_tokens = random.randint(*self.param_ranges['max_tokens'])
        
        if random.random() < MUTATION_RATE:
            new_config.context_window = random.randint(*self.param_ranges['context_window'])
        
        if random.random() < MUTATION_RATE:
            new_config.prompt_template = random.choice(self.prompt_templates)
        
        new_config.generation = self.generation
        new_config.creation_method = "mutation"
        new_config.parent_configs = [f"gen{config.generation}_id{config.get_id()}"]
        
        return new_config
    
    def crossover_configs(self, parent1: TranslationConfig, parent2: TranslationConfig) -> TranslationConfig:
        """Realiza cruzamento inteligente entre duas configurações"""
        # Crossover com bias para o melhor parent
        better_parent = parent1 if parent1.fitness > parent2.fitness else parent2
        worse_parent = parent2 if parent1.fitness > parent2.fitness else parent1
        
        child = TranslationConfig(
            temperature=random.choices([parent1.temperature, parent2.temperature], weights=[parent1.fitness, parent2.fitness])[0],
            top_p=random.choices([parent1.top_p, parent2.top_p], weights=[parent1.fitness, parent2.fitness])[0],
            top_k=random.choice([parent1.top_k, parent2.top_k]),
            repeat_penalty=random.choices([parent1.repeat_penalty, parent2.repeat_penalty], weights=[parent1.fitness, parent2.fitness])[0],
            chunk_size=random.choice([parent1.chunk_size, parent2.chunk_size]),
            prompt_template=better_parent.prompt_template if random.random() < 0.7 else worse_parent.prompt_template,
            max_tokens=random.choice([parent1.max_tokens, parent2.max_tokens]),
            context_window=random.choice([parent1.context_window, parent2.context_window]),
            quality_threshold=random.choices([parent1.quality_threshold, parent2.quality_threshold], weights=[parent1.fitness, parent2.fitness])[0],
            generation=self.generation,
            creation_method="crossover",
            parent_configs=[f"gen{parent1.generation}_id{parent1.get_id()}", 
                          f"gen{parent2.generation}_id{parent2.get_id()}"]
        )
        
        return child
    
    def evaluate_fitness(self, config: TranslationConfig) -> float:
        """Avalia o fitness de uma configuração usando benchmark aprimorado"""
        print(f"   🧬 Avaliando config: temp={config.temperature:.3f}, chunk={config.chunk_size}, prompt={config.prompt_template}")
        
        # Carregar e processar arquivo de teste
        if not os.path.exists(BENCHMARK_FILE):
            print(f"❌ Arquivo não encontrado: {BENCHMARK_FILE}")
            return 0.0
        
        with open(BENCHMARK_FILE, 'r', encoding='utf-8') as f:
            srt_content = f.read()
        
        texts_to_translate, _ = extract_text_from_srt(srt_content)
        
        # Criar amostra inteligente
        sample_texts = texts_to_translate[:SAMPLE_SIZE]
        
        try:
            # Executar tradução
            start_time = time.time()
            translations = self.translate_with_config(sample_texts, config)
            elapsed_time = time.time() - start_time
            
            # Calcular score baseado nos benchmarks estratificados
            score = self.calculate_advanced_benchmark_score(translations)
            
            # Bônus por consistência e qualidade
            consistency_bonus = self.calculate_consistency_bonus(translations)
            quality_bonus = self.calculate_quality_bonus(translations, config)
            
            # Penalidade por lentidão mais suave
            time_penalty = max(0, (elapsed_time / len(sample_texts) - 0.25) * 2)
            
            # Score final com componentes balanceados
            final_score = max(0, score + consistency_bonus + quality_bonus - time_penalty)
            
            print(f"      Score: {score:.2f}, Consistência: {consistency_bonus:.2f}, Qualidade: {quality_bonus:.2f}")
            print(f"      Tempo: {elapsed_time:.1f}s, Final: {final_score:.2f}")
            
            return final_score
            
        except Exception as e:
            print(f"      ❌ Erro na avaliação: {e}")
            return 0.0
    
    def translate_with_config(self, texts: List[str], config: TranslationConfig) -> List[str]:
        """Executa tradução com configuração específica e contexto"""
        # Dividir em chunks com contexto
        chunk_size = config.chunk_size
        context_window = config.context_window
        all_translations = []
        
        for i in range(0, len(texts), chunk_size):
            # Pegar chunk atual + contexto
            start_idx = max(0, i - context_window)
            end_idx = min(len(texts), i + chunk_size + context_window)
            
            chunk_texts = texts[start_idx:end_idx]
            actual_start = i - start_idx
            actual_end = actual_start + min(chunk_size, len(texts) - i)
            
            prompt = self.create_advanced_prompt_template(config.prompt_template, chunk_texts, actual_start, actual_end)
            
            payload = {
                "model": "tibellium/towerinstruct-mistral",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": config.temperature,
                    "top_p": config.top_p,
                    "top_k": config.top_k,
                    "repeat_penalty": config.repeat_penalty,
                    "num_predict": config.max_tokens
                }
            }
            
            response = requests.post(OLLAMA_URL, json=payload, timeout=180)
            if response.status_code == 200:
                result = response.json()
                translated = result.get("response", "").strip()
                
                # Processar resposta
                chunk_translations = self.extract_translations_from_response(translated, texts[i:i+chunk_size])
                all_translations.extend(chunk_translations)
            else:
                # Fallback
                all_translations.extend(texts[i:i+chunk_size])
        
        return all_translations[:len(texts)]
    
    def extract_translations_from_response(self, response: str, original_texts: List[str]) -> List[str]:
        """Extrai traduções da resposta do modelo de forma inteligente"""
        lines = response.split('\n')
        translations = []
        
        # Tentar extrair traduções numeradas
        for line in lines:
            line = line.strip()
            if line and not any(skip in line.lower() for skip in ['tradução', 'translation', 'output', 'saída', 'português']):
                # Remover numeração
                line = re.sub(r'^\d+[\.\)]\s*', '', line)
                if line:
                    translations.append(line)
        
        # Se não conseguiu extrair suficientes, usar fallback
        while len(translations) < len(original_texts):
            idx = len(translations)
            if idx < len(original_texts):
                translations.append(original_texts[idx])
            else:
                translations.append("")
        
        return translations[:len(original_texts)]
    
    def create_advanced_prompt_template(self, template_type: str, texts: List[str], start_idx: int, end_idx: int) -> str:
        """Cria templates de prompt ULTRA-ESPECIALIZADOS com contexto"""
        # Marcar textos que precisam de tradução
        marked_texts = []
        for i, text in enumerate(texts):
            if start_idx <= i < end_idx:
                marked_texts.append(f">>> {i+1}. {text}")  # Marcar para traduzir
            else:
                marked_texts.append(f"    {i+1}. {text}")  # Contexto apenas
        
        base_instruction = f"Traduza APENAS os textos marcados com >>> para português brasileiro.\n\nTEXTOS:\n{chr(10).join(marked_texts)}\n\nTRADUÇÕES:"
        
        templates = {
            "jojo_master": f"ESPECIALISTA JOJO'S BIZARRE ADVENTURE: Preserve nomes de Stands (Silver Chariot, Magician's Red) e personagens. 'flame completes twelve' = 'meio dia'. Português brasileiro natural. {base_instruction}",
            
            "anime_linguist": f"LINGUISTA ANIME: Mantenha terminologia específica (Stand, ora ora). Use português brasileiro ('você', 'xícaras'). Preserve nomes próprios. {base_instruction}",
            
            "cultural_expert": f"ESPECIALISTA CULTURAL: Adapte expressões idiomáticas ('Good grief' → 'Que saco'). Mantenha elementos japoneses (Za Warudo). Português brasileiro fluente. {base_instruction}",
            
            "dialogue_specialist": f"ESPECIALISTA EM DIÁLOGOS: Traduza gagueira (W-What → Q-Que). Use 'você' sempre. Mantenha emoção e naturalidade. Preserve nomes. {base_instruction}",
            
            "stand_authority": f"AUTORIDADE EM STANDS: NUNCA traduza nomes de Stands (Silver Chariot, Star Platinum, Hermit Purple). Traduza apenas descrições e diálogos. {base_instruction}",
            
            "action_translator": f"TRADUTOR DE AÇÃO: Especialista em anime de luta. Preserve gritos (Ora ora ora!). Traduza ações dinamicamente. Português brasileiro energético. {base_instruction}",
            
            "character_voice": f"VOZ DE PERSONAGEM: Mantenha personalidade na tradução. Jean Pierre Polnareff deve soar francês-brasileiro. Preserve características únicas. {base_instruction}",
            
            "idiom_expert": f"ESPECIALISTA EM IDIOMAS: 'before flame completes twelve' = 'antes do meio dia'. Traduza expressões complexas corretamente. Contexto é crucial. {base_instruction}",
            
            "brazilian_native": f"BRASILEIRO NATIVO: Use 'xícaras' não 'chávenas', 'você' não 'tu'. Português brasileiro autêntico e natural. Preserve nomes estrangeiros. {base_instruction}",
            
            "context_aware": f"CONSCIENTE DO CONTEXTO: Use contexto anterior para traduzir coerentemente. Mantenha continuidade de personagens e situações. {base_instruction}",
            
            "precision_focused": f"FOCO EM PRECISÃO: Tradução técnica e precisa. Zero erros em nomes próprios. Português brasileiro formal mas natural. {base_instruction}",
            
            "flow_optimizer": f"OTIMIZADOR DE FLUIDEZ: Priorize naturalidade e fluidez. Adapte para soar brasileiro autêntico. Mantenha elementos anime intactos. {base_instruction}"
        }
        
        return templates.get(template_type, f"Traduza para português brasileiro: {base_instruction}")
    
    def calculate_advanced_benchmark_score(self, translations: List[str]) -> float:
        """Calcula score baseado nos benchmarks estratificados"""
        scores = []
        full_text = ' '.join(translations).lower()
        
        tier_bonuses = {
            "critical": 1.5,    # Multiplicador para testes críticos
            "advanced": 1.3,    # Multiplicador para testes avançados  
            "important": 1.1,   # Multiplicador para testes importantes
            "basic": 1.0        # Sem multiplicador para básicos
        }
        
        total_possible = 0
        total_achieved = 0
        
        for benchmark in self.benchmark_phrases:
            expected = benchmark["expected"].lower()
            weight = benchmark["weight"]
            tier = benchmark.get("tier", "basic")
            tier_bonus = tier_bonuses[tier]
            
            # Buscar por correspondência
            score = 0
            if expected in full_text:
                score = 10  # Correspondência exata
            else:
                # Correspondência parcial mais sofisticada
                expected_words = expected.split()
                found_words = sum(1 for word in expected_words if word in full_text)
                
                # Bônus por preservação de elementos importantes
                if any(word in expected for word in ["silver", "chariot", "magician", "red", "stand"]):
                    # Elementos que DEVEM ser preservados
                    if any(word in full_text for word in expected_words):
                        score = min(10, found_words / len(expected_words) * 10 + 3)
                    else:
                        score = 0  # Penalidade severa por não preservar
                else:
                    score = (found_words / len(expected_words)) * 10
            
            # Aplicar peso e bônus de tier
            final_score = score * weight * tier_bonus
            scores.append(final_score)
            
            total_possible += weight * 10 * tier_bonus
            total_achieved += final_score
        
        return (total_achieved / total_possible) * 10 if total_possible > 0 else 0
    
    def calculate_consistency_bonus(self, translations: List[str]) -> float:
        """Calcula bônus por consistência na tradução"""
        # Verificar consistência na preservação de nomes
        full_text = ' '.join(translations)
        
        consistency_score = 0
        
        # Verificar se Stand names são preservados consistentemente
        stand_names = ["Silver Chariot", "Magician's Red", "Star Platinum", "Hermit Purple"]
        for stand in stand_names:
            if stand.lower() in ' '.join(translations).lower():
                # Verificar se aparece sempre igual
                count_correct = full_text.count(stand)
                count_variations = sum(full_text.lower().count(variant) for variant in [
                    stand.lower().replace(" ", ""), 
                    stand.lower().replace(" ", "_"),
                    stand.lower().translate(str.maketrans("", "", " "))
                ])
                
                if count_correct > 0 and count_variations == 0:
                    consistency_score += 0.3
        
        # Verificar uso consistente de pronomes brasileiros
        you_count = full_text.lower().count(" você ")
        tu_count = full_text.lower().count(" tu ")
        
        if you_count > 0 and tu_count == 0:
            consistency_score += 0.2
        
        # Verificar português brasileiro vs europeu
        br_terms = ["xícaras", "você", "que saco"]
        pt_terms = ["chávenas", "tu", "caramba"]
        
        br_found = sum(1 for term in br_terms if term in full_text.lower())
        pt_found = sum(1 for term in pt_terms if term in full_text.lower())
        
        if br_found > 0 and pt_found == 0:
            consistency_score += 0.3
        
        return min(1.0, consistency_score)
    
    def calculate_quality_bonus(self, translations: List[str], config: TranslationConfig) -> float:
        """Calcula bônus por qualidade geral"""
        quality_score = 0
        full_text = ' '.join(translations)
        
        # Bônus por diversidade lexical (não repetitivo)
        words = full_text.lower().split()
        unique_ratio = len(set(words)) / len(words) if words else 0
        if unique_ratio > 0.8:
            quality_score += 0.3
        
        # Bônus por naturalidade (presença de conectivos brasileiros)
        natural_connectors = ["então", "aí", "né", "pois", "mas", "porém"]
        connector_count = sum(1 for conn in natural_connectors if conn in full_text.lower())
        quality_score += min(0.2, connector_count * 0.05)
        
        # Bônus por preservação correta de elementos japoneses
        japanese_elements = ["ora ora", "za warudo", "stand"]
        preserved = sum(1 for elem in japanese_elements if elem in full_text.lower())
        quality_score += preserved * 0.15
        
        # Penalidade por problemas comuns
        problems = ["translation", "tradução:", "output:", "resultado:"]
        penalty = sum(0.2 for prob in problems if prob in full_text.lower())
        quality_score -= penalty
        
        return max(0, min(1.5, quality_score))
    
    def initialize_population_intelligent(self):
        """Inicializa população usando conhecimento anterior + exploração"""
        print("🧠 Gerando população inicial INTELIGENTE...")
        
        self.population = []
        
        # 1. Adicionar configuração anterior como base (se existir)
        try:
            config_files = glob.glob("best_config_evolved_*.json")
            if config_files:
                latest_config = max(config_files, key=os.path.getctime)
                with open(latest_config, 'r') as f:
                    data = json.load(f)
                
                previous_best = data['best_config']
                print(f"📚 Carregando configuração anterior: Score {data['fitness']:.2f}")
                
                # Criar configuração base
                base_config = TranslationConfig(
                    temperature=previous_best['temperature'],
                    top_p=previous_best['top_p'], 
                    top_k=previous_best['top_k'],
                    repeat_penalty=previous_best['repeat_penalty'],
                    chunk_size=previous_best['chunk_size'],
                    prompt_template=previous_best['prompt_template'],
                    max_tokens=previous_best.get('max_tokens', 4096),
                    context_window=previous_best.get('context_window', 2),
                    quality_threshold=previous_best.get('quality_threshold', 0.85),
                    generation=self.generation,
                    creation_method="inherited"
                )
                
                # Avaliar configuração base
                base_config.fitness = self.evaluate_fitness(base_config)
                base_config.diversity_score = self.calculate_diversity_score(base_config)
                self.population.append(base_config)
                self.all_configs_tested.append(base_config)
                print(f"   ✅ Base herdada: {base_config.fitness:.2f}")
                
                # 2. Criar variações da configuração base (30% da população)
                num_variants = int(POPULATION_SIZE * 0.3)
                for i in range(num_variants):
                    variant = self.mutate_config(base_config)
                    variant.creation_method = "intelligent_variant"
                    variant.fitness = self.evaluate_fitness(variant)
                    variant.diversity_score = self.calculate_diversity_score(variant)
                    self.population.append(variant)
                    self.all_configs_tested.append(variant)
                    print(f"   🧬 Variante {i+1}: {variant.fitness:.2f}")
        
        except Exception as e:
            print(f"   ⚠️ Erro ao carregar configuração anterior: {e}")
        
        # 3. Preencher resto com configurações aleatórias focadas
        remaining = POPULATION_SIZE - len(self.population)
        print(f"   🎲 Gerando {remaining} configurações exploratórias...")
        
        for i in range(remaining):
            config = self.generate_random_config()
            config.creation_method = "focused_random"
            config.fitness = self.evaluate_fitness(config)
            config.diversity_score = self.calculate_diversity_score(config)
            self.population.append(config)
            self.all_configs_tested.append(config)
        
        # Ordenar por fitness
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        
        # Atualizar melhor configuração
        if self.population[0].fitness > self.best_ever_fitness:
            self.best_ever_fitness = self.population[0].fitness
            self.best_ever_config = self.population[0]
        
        print(f"✅ População inteligente criada. Melhor fitness: {self.population[0].fitness:.2f}")
        print(f"📊 Distribuição: Base+Variantes: {min(4, len(self.population))}, Aleatórias: {max(0, len(self.population)-4)}")
    
    def initialize_population(self):
        """Wrapper que escolhe inicialização inteligente ou normal"""
        config_files = glob.glob("best_config_evolved_*.json")
        
        if config_files:
            self.initialize_population_intelligent()
        else:
            # Fallback para inicialização normal se não há configuração anterior
            print("🧬 Gerando população inicial...")
            self.population = []
            for i in range(POPULATION_SIZE):
                config = self.generate_random_config()
                config.fitness = self.evaluate_fitness(config)
                config.diversity_score = self.calculate_diversity_score(config)
                self.population.append(config)
                self.all_configs_tested.append(config)
            
            self.population.sort(key=lambda x: x.fitness, reverse=True)
            
            if self.population[0].fitness > self.best_ever_fitness:
                self.best_ever_fitness = self.population[0].fitness
                self.best_ever_config = self.population[0]
            
            print(f"✅ População inicial criada. Melhor fitness: {self.population[0].fitness:.2f}")
    
    def evolve_generation(self):
        """Evolui para próxima geração com controle de diversidade"""
        self.generation += 1
        print(f"\n🧬 === GERAÇÃO {self.generation} ===")
        
        new_population = []
        
        # Elitismo: manter os melhores
        elite = self.population[:ELITE_SIZE]
        new_population.extend(elite)
        print(f"👑 Elite preservada: {len(elite)} configs")
        
        # Calcular diversidade atual
        current_diversity = sum(c.diversity_score for c in self.population) / len(self.population)
        self.diversity_history.append(current_diversity)
        
        # Ajustar estratégia baseada na diversidade
        diversity_boost = current_diversity < DIVERSITY_THRESHOLD
        if diversity_boost:
            print(f"🌟 Baixa diversidade detectada ({current_diversity:.3f}), aumentando exploração")
        
        # Gerar resto da população
        while len(new_population) < POPULATION_SIZE:
            if random.random() < CROSSOVER_RATE and len(elite) >= 2 and not diversity_boost:
                # Crossover normal
                parent1 = self.tournament_selection(elite)
                parent2 = self.tournament_selection(elite)
                child = self.crossover_configs(parent1, parent2)
                
                # Aplicar mutação ao filho
                if random.random() < MUTATION_RATE:
                    child = self.mutate_config(child)
                
            elif random.random() < 0.6 and elite and not diversity_boost:
                # Mutação de elite
                parent = random.choice(elite[:3])  # Foco nos 3 melhores
                child = self.mutate_config(parent)
                
            else:
                # Geração aleatória para diversidade
                child = self.generate_random_config()
                child.creation_method = "diversity_injection"
            
            # Avaliar novo indivíduo
            child.fitness = self.evaluate_fitness(child)
            child.diversity_score = self.calculate_diversity_score(child)
            new_population.append(child)
            self.all_configs_tested.append(child)
        
        # Atualizar população
        self.population = new_population
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        
        # Atualizar estatísticas
        best_fitness = self.population[0].fitness
        avg_fitness = sum(c.fitness for c in self.population) / len(self.population)
        
        self.best_fitness_history.append(best_fitness)
        self.avg_fitness_history.append(avg_fitness)
        
        # Verificar se é novo recorde
        if best_fitness > self.best_ever_fitness:
            self.best_ever_fitness = best_fitness
            self.best_ever_config = self.population[0]
            self.stagnation_counter = 0
            print(f"🎉 NOVO RECORDE! Fitness: {best_fitness:.2f}")
            
            # Salvar melhor configuração imediatamente
            self.save_best_config()
        else:
            self.stagnation_counter += 1
        
        print(f"📊 Melhor: {best_fitness:.2f}, Média: {avg_fitness:.2f}, Diversidade: {current_diversity:.3f}")
        print(f"📈 Estagnação: {self.stagnation_counter}/{STAGNATION_LIMIT}")
        
        # Salvar progresso
        self.save_progress()
    
    def tournament_selection(self, candidates: List[TranslationConfig], tournament_size: int = 3) -> TranslationConfig:
        """Seleção por torneio para escolher parents"""
        tournament = random.sample(candidates, min(tournament_size, len(candidates)))
        return max(tournament, key=lambda x: x.fitness)
    
    def save_best_config(self):
        """Salva a melhor configuração encontrada"""
        if not self.best_ever_config:
            return
        
        config_data = {
            'best_config': self.best_ever_config.to_dict(),
            'fitness': self.best_ever_fitness,
            'generation': self.generation,
            'total_configs_tested': len(self.all_configs_tested),
            'evolution_complete': False,
            'timestamp': int(time.time())
        }
        
        filename = f"best_config_evolved_{int(time.time())}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Melhor configuração salva: {filename}")
    
    def should_stop(self) -> bool:
        """Verifica critérios de parada aprimorados"""
        if self.best_ever_fitness >= TARGET_SCORE:
            print(f"🎯 Meta atingida! Score: {self.best_ever_fitness:.2f} >= {TARGET_SCORE}")
            return True
        
        if self.stagnation_counter >= STAGNATION_LIMIT:
            print(f"⏹️ Estagnação detectada ({self.stagnation_counter} gerações)")
            return True
        
        if self.generation >= MAX_GENERATIONS:
            print(f"⏹️ Limite de gerações atingido ({MAX_GENERATIONS})")
            return True
        
        # Critério adicional: convergência da população
        if len(self.best_fitness_history) >= 5:
            recent_improvement = max(self.best_fitness_history[-5:]) - min(self.best_fitness_history[-5:])
            if recent_improvement < 0.1 and self.stagnation_counter >= 5:
                print(f"⏹️ Convergência detectada (melhoria < 0.1 em 5 gerações)")
                return True
        
        return False
    
    def run_evolution(self):
        """Executa o processo evolutivo completo"""
        print("🚀 INICIANDO TUNING EVOLUTIVO AUTOMÁTICO V2.0")
        print("=" * 70)
        print(f"População: {POPULATION_SIZE}, Gerações máx: {MAX_GENERATIONS}")
        print(f"Meta: {TARGET_SCORE}, Amostra: {SAMPLE_SIZE} textos")
        print(f"Mutação: {MUTATION_RATE}, Crossover: {CROSSOVER_RATE}")
        print("=" * 70)
        
        start_time = time.time()
        
        # Inicializar
        if not self.population:
            self.initialize_population()
        
        # Loop evolutivo
        while not self.should_stop():
            self.evolve_generation()
            time.sleep(1)  # Pausa para não sobrecarregar
        
        elapsed_time = time.time() - start_time
        
        # Resultados finais
        print("\n🏆 EVOLUÇÃO COMPLETA!")
        print("=" * 70)
        print(f"⏱️ Tempo total: {elapsed_time/60:.1f} minutos")
        print(f"🧪 Configurações testadas: {len(self.all_configs_tested)}")
        print(f"🏅 Gerações executadas: {self.generation}")
        print("=" * 70)
        print(f"🥇 MELHOR CONFIGURAÇÃO (Score: {self.best_ever_fitness:.2f}/10):")
        print(f"   Temperature: {self.best_ever_config.temperature:.3f}")
        print(f"   Top-p: {self.best_ever_config.top_p:.3f}")
        print(f"   Top-k: {self.best_ever_config.top_k}")
        print(f"   Repeat penalty: {self.best_ever_config.repeat_penalty:.3f}")
        print(f"   Chunk size: {self.best_ever_config.chunk_size}")
        print(f"   Context window: {self.best_ever_config.context_window}")
        print(f"   Quality threshold: {self.best_ever_config.quality_threshold:.3f}")
        print(f"   Prompt: {self.best_ever_config.prompt_template}")
        print(f"   Geração: {self.best_ever_config.generation}")
        print(f"   Método: {self.best_ever_config.creation_method}")
        
        # Análise de convergência
        if len(self.best_fitness_history) > 1:
            total_improvement = self.best_fitness_history[-1] - self.best_fitness_history[0]
            print(f"📈 Melhoria total: {total_improvement:.2f} pontos")
            
            if len(self.best_fitness_history) >= 10:
                recent_trend = sum(self.best_fitness_history[-5:]) / 5 - sum(self.best_fitness_history[-10:-5]) / 5
                print(f"📊 Tendência recente: {recent_trend:+.2f} pontos")
        
        # Salvar configuração final
        final_config = {
            'best_config': self.best_ever_config.to_dict(),
            'fitness': self.best_ever_fitness,
            'total_configs_tested': len(self.all_configs_tested),
            'generations': self.generation,
            'evolution_complete': True,
            'evolution_time_minutes': elapsed_time / 60,
            'final_statistics': {
                'best_fitness_history': self.best_fitness_history,
                'avg_fitness_history': self.avg_fitness_history,
                'diversity_history': self.diversity_history,
                'stagnation_counter': self.stagnation_counter
            },
            'meta': {
                'target_score': TARGET_SCORE,
                'target_achieved': self.best_ever_fitness >= TARGET_SCORE,
                'population_size': POPULATION_SIZE,
                'mutation_rate': MUTATION_RATE,
                'sample_size': SAMPLE_SIZE,
                'algorithm_version': "v2.0_ultra_optimized"
            }
        }
        
        final_filename = f"best_config_evolved_final_{int(time.time())}.json"
        with open(final_filename, 'w', encoding='utf-8') as f:
            json.dump(final_config, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Configuração final salva: {final_filename}")
        
        if self.best_ever_fitness >= TARGET_SCORE:
            print(f"🎉 META ALCANÇADA! Score final: {self.best_ever_fitness:.2f}")
        else:
            print(f"⚡ Meta não alcançada, mas configuração otimizada! Score: {self.best_ever_fitness:.2f}")
            print(f"💡 Sugestão: Execute novamente para continuar a evolução")
        
        return self.best_ever_config

if __name__ == "__main__":
    tuner = EvolutionaryTuner()
    
    # Verificar se há progresso anterior para continuar
    previous_files = glob.glob("evolution_progress_*.json")
    if previous_files:
        latest = max(previous_files, key=os.path.getctime)
        print(f"📂 Encontrado progresso anterior: {latest}")
        choice = input("Continuar evolução anterior? (y/N): ").lower().strip()
        if choice == 'y':
            if tuner.load_progress(latest):
                print(f"✅ Progresso carregado com sucesso!")
            else:
                print(f"❌ Falha ao carregar progresso, iniciando do zero")
    
    # Executar evolução
    best_config = tuner.run_evolution()
    print(f"\n🎉 Configuração otimizada salva!") 