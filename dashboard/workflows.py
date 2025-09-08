"""
Engine de Workflow avançado para o iConnect.
Gerencia fluxos personalizáveis e regras de automação.
"""
import logging
import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from .models import Ticket, WorkflowRule, WorkflowExecution, InteracaoTicket
from .notifications import notification_service

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Engine principal para execução de workflows"""
    
    def __init__(self):
        self.workflow_config = getattr(settings, 'WORKFLOW_CONFIG', {})
    
    def execute_workflow(self, ticket, trigger_event, user=None):
        """Executa workflow baseado no evento disparador"""
        try:
            # Buscar regras aplicáveis
            applicable_rules = self._get_applicable_rules(ticket, trigger_event)
            
            results = []
            for rule in applicable_rules:
                result = self._execute_rule(rule, ticket, user)
                results.append(result)
                
                # Log da execução
                WorkflowExecution.objects.create(
                    ticket=ticket,
                    rule=rule,
                    trigger_event=trigger_event,
                    execution_result=json.dumps(result),
                    executed_by=user
                )
            
            logger.info(f"Workflow executado para ticket #{ticket.numero} - {len(results)} regras processadas")
            return results
            
        except Exception as e:
            logger.error(f"Erro na execução do workflow: {str(e)}")
            return []
    
    def _get_applicable_rules(self, ticket, trigger_event):
        """Retorna regras aplicáveis ao ticket e evento"""
        try:
            # Buscar regras ativas para o evento
            rules = WorkflowRule.objects.filter(
                is_active=True,
                trigger_event=trigger_event
            )
            
            applicable_rules = []
            
            for rule in rules:
                if self._check_rule_conditions(rule, ticket):
                    applicable_rules.append(rule)
            
            # Ordenar por prioridade
            applicable_rules.sort(key=lambda r: r.priority, reverse=True)
            
            return applicable_rules
            
        except Exception as e:
            logger.error(f"Erro ao buscar regras aplicáveis: {str(e)}")
            return []
    
    def _check_rule_conditions(self, rule, ticket):
        """Verifica se as condições da regra são atendidas"""
        try:
            conditions = json.loads(rule.conditions) if rule.conditions else {}
            
            # Verificar categoria
            if 'categoria' in conditions:
                if ticket.categoria_id not in conditions['categoria']:
                    return False
            
            # Verificar prioridade
            if 'prioridade' in conditions:
                if ticket.prioridade not in conditions['prioridade']:
                    return False
            
            # Verificar status
            if 'status' in conditions:
                if ticket.status not in conditions['status']:
                    return False
            
            # Verificar tempo desde criação
            if 'time_since_creation' in conditions:
                time_condition = conditions['time_since_creation']
                time_since = timezone.now() - ticket.criado_em
                
                if 'min_hours' in time_condition:
                    if time_since.total_seconds() < time_condition['min_hours'] * 3600:
                        return False
                
                if 'max_hours' in time_condition:
                    if time_since.total_seconds() > time_condition['max_hours'] * 3600:
                        return False
            
            # Verificar se agente está atribuído
            if 'has_agent' in conditions:
                has_agent = ticket.agente is not None
                if conditions['has_agent'] != has_agent:
                    return False
            
            # Verificar número de interações
            if 'interaction_count' in conditions:
                interaction_count = ticket.interacoes.count()
                count_condition = conditions['interaction_count']
                
                if 'min' in count_condition and interaction_count < count_condition['min']:
                    return False
                if 'max' in count_condition and interaction_count > count_condition['max']:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao verificar condições da regra: {str(e)}")
            return False
    
    def _execute_rule(self, rule, ticket, user):
        """Executa uma regra específica"""
        try:
            actions = json.loads(rule.actions) if rule.actions else {}
            results = {'rule_id': rule.id, 'actions_executed': []}
            
            for action_type, action_config in actions.items():
                result = self._execute_action(action_type, action_config, ticket, user)
                results['actions_executed'].append({
                    'type': action_type,
                    'result': result
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Erro ao executar regra {rule.id}: {str(e)}")
            return {'error': str(e)}
    
    def _execute_action(self, action_type, action_config, ticket, user):
        """Executa uma ação específica"""
        try:
            if action_type == 'change_status':
                old_status = ticket.status
                ticket.status = action_config['new_status']
                ticket.save()
                
                # Log da mudança
                InteracaoTicket.objects.create(
                    ticket=ticket,
                    usuario=None,  # Sistema
                    tipo='sistema',
                    conteudo=f'Status alterado automaticamente de "{old_status}" para "{ticket.status}" por workflow.',
                    publico=False
                )
                
                return f"Status alterado para {ticket.status}"
            
            elif action_type == 'change_priority':
                old_priority = ticket.prioridade
                ticket.prioridade = action_config['new_priority']
                ticket.save()
                
                InteracaoTicket.objects.create(
                    ticket=ticket,
                    usuario=None,
                    tipo='sistema',
                    conteudo=f'Prioridade alterada automaticamente de "{old_priority}" para "{ticket.prioridade}" por workflow.',
                    publico=False
                )
                
                return f"Prioridade alterada para {ticket.prioridade}"
            
            elif action_type == 'assign_agent':
                if action_config.get('auto_assign'):
                    from .automation import auto_assignment_engine
                    agent = auto_assignment_engine.assign_ticket(ticket)
                    if agent:
                        return f"Ticket atribuído automaticamente a {agent.username}"
                    else:
                        return "Nenhum agente disponível para atribuição"
                
                elif action_config.get('specific_agent_id'):
                    try:
                        agent = User.objects.get(id=action_config['specific_agent_id'])
                        ticket.agente = agent
                        ticket.save()
                        
                        InteracaoTicket.objects.create(
                            ticket=ticket,
                            usuario=None,
                            tipo='sistema',
                            conteudo=f'Ticket atribuído automaticamente a {agent.username} por workflow.',
                            publico=False
                        )
                        
                        return f"Ticket atribuído a {agent.username}"
                    except User.DoesNotExist:
                        return "Agente especificado não encontrado"
            
            elif action_type == 'send_notification':
                recipients = action_config.get('recipients', [])
                message_template = action_config.get('message', 'Notificação automática do workflow')
                
                for recipient_type in recipients:
                    if recipient_type == 'agent' and ticket.agente:
                        notification_service.send_ticket_notification(
                            ticket=ticket,
                            event_type='workflow_notification',
                            recipient_email=ticket.agente.email,
                            extra_context={'message': message_template}
                        )
                    elif recipient_type == 'client':
                        notification_service.send_ticket_notification(
                            ticket=ticket,
                            event_type='workflow_notification',
                            recipient_email=ticket.cliente.email,
                            extra_context={'message': message_template}
                        )
                
                return f"Notificações enviadas para: {', '.join(recipients)}"
            
            elif action_type == 'add_comment':
                comment = action_config.get('comment', 'Comentário automático do workflow')
                is_public = action_config.get('public', False)
                
                InteracaoTicket.objects.create(
                    ticket=ticket,
                    usuario=None,
                    tipo='sistema',
                    conteudo=comment,
                    publico=is_public
                )
                
                return f"Comentário adicionado ({'público' if is_public else 'privado'})"
            
            elif action_type == 'escalate':
                escalation_level = action_config.get('level', 1)
                
                # Aumentar prioridade
                priority_escalation = {
                    'baixa': 'media',
                    'media': 'alta',
                    'alta': 'critica'
                }
                
                if ticket.prioridade in priority_escalation:
                    old_priority = ticket.prioridade
                    ticket.prioridade = priority_escalation[ticket.prioridade]
                    ticket.save()
                    
                    InteracaoTicket.objects.create(
                        ticket=ticket,
                        usuario=None,
                        tipo='sistema',
                        conteudo=f'Ticket escalado automaticamente (nível {escalation_level}). Prioridade alterada de "{old_priority}" para "{ticket.prioridade}".',
                        publico=False
                    )
                    
                    return f"Ticket escalado para nível {escalation_level}"
                
                return "Ticket já está na prioridade máxima"
            
            else:
                return f"Tipo de ação não reconhecida: {action_type}"
                
        except Exception as e:
            logger.error(f"Erro ao executar ação {action_type}: {str(e)}")
            return f"Erro: {str(e)}"
    
    def get_available_workflows(self, categoria=None):
        """Retorna workflows disponíveis para uma categoria"""
        try:
            default_workflows = self.workflow_config.get('DEFAULT_WORKFLOWS', {})
            
            if categoria and categoria.nome.lower() in default_workflows:
                return default_workflows[categoria.nome.lower()]
            else:
                # Retornar workflow padrão
                return default_workflows.get('suporte_tecnico', [
                    'aberto', 'em_andamento', 'aguardando_cliente', 'resolvido', 'fechado'
                ])
                
        except Exception as e:
            logger.error(f"Erro ao buscar workflows disponíveis: {str(e)}")
            return ['aberto', 'em_andamento', 'resolvido', 'fechado']
    
    def get_workflow_metrics(self, days=30):
        """Retorna métricas de execução de workflows"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            executions = WorkflowExecution.objects.filter(
                created_at__gte=cutoff_date
            )
            
            total_executions = executions.count()
            successful_executions = executions.filter(
                execution_result__icontains='actions_executed'
            ).count()
            
            # Top regras mais executadas
            top_rules = executions.values('rule__name').annotate(
                count=models.Count('id')
            ).order_by('-count')[:5]
            
            return {
                'total_executions': total_executions,
                'successful_executions': successful_executions,
                'success_rate': (successful_executions / total_executions * 100) if total_executions > 0 else 0,
                'top_rules': list(top_rules)
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular métricas de workflow: {str(e)}")
            return {
                'total_executions': 0,
                'successful_executions': 0,
                'success_rate': 0,
                'top_rules': []
            }


class WorkflowBuilder:
    """Construtor visual de workflows"""
    
    def create_rule(self, name, description, trigger_event, conditions, actions, priority=1):
        """Cria uma nova regra de workflow"""
        try:
            rule = WorkflowRule.objects.create(
                name=name,
                description=description,
                trigger_event=trigger_event,
                conditions=json.dumps(conditions),
                actions=json.dumps(actions),
                priority=priority,
                is_active=True
            )
            
            logger.info(f"Nova regra de workflow criada: {name}")
            return rule
            
        except Exception as e:
            logger.error(f"Erro ao criar regra de workflow: {str(e)}")
            return None
    
    def get_rule_template(self, template_name):
        """Retorna template de regra pré-definida"""
        templates = {
            'auto_assign_high_priority': {
                'name': 'Auto-atribuição para Alta Prioridade',
                'description': 'Atribui automaticamente tickets de alta prioridade',
                'trigger_event': 'ticket_created',
                'conditions': {'prioridade': ['alta', 'critica']},
                'actions': {
                    'assign_agent': {'auto_assign': True},
                    'send_notification': {
                        'recipients': ['agent'],
                        'message': 'Novo ticket de alta prioridade atribuído'
                    }
                },
                'priority': 9
            },
            'escalate_old_tickets': {
                'name': 'Escalação por Tempo',
                'description': 'Escala tickets antigos sem resposta',
                'trigger_event': 'ticket_updated',
                'conditions': {
                    'status': ['aberto', 'em_andamento'],
                    'time_since_creation': {'min_hours': 24}
                },
                'actions': {
                    'escalate': {'level': 1},
                    'add_comment': {
                        'comment': 'Ticket escalado automaticamente devido ao tempo de resposta.',
                        'public': False
                    }
                },
                'priority': 5
            },
            'close_resolved_tickets': {
                'name': 'Fechar Tickets Resolvidos',
                'description': 'Fecha automaticamente tickets resolvidos há mais de 48h',
                'trigger_event': 'ticket_updated',
                'conditions': {
                    'status': ['resolvido'],
                    'time_since_creation': {'min_hours': 48}
                },
                'actions': {
                    'change_status': {'new_status': 'fechado'},
                    'add_comment': {
                        'comment': 'Ticket fechado automaticamente após 48h sem atividade.',
                        'public': True
                    }
                },
                'priority': 3
            }
        }
        
        return templates.get(template_name)


# Instâncias globais
workflow_engine = WorkflowEngine()
workflow_builder = WorkflowBuilder()
