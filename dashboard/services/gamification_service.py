"""
Gamification Service — Pontos, badges, leaderboard para agentes
"""
import logging
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Avg, Count, F, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


class GamificationService:
    """Servico de gamificacao para motivacao de agentes"""

    # Pontos por ação
    POINTS = {
        'ticket_resolved': 10,
        'ticket_closed': 5,
        'first_response_sla': 15,  # Respondeu dentro do SLA
        'resolution_sla': 20,  # Resolveu dentro do SLA
        'csat_5_stars': 25,
        'csat_4_stars': 10,
        'kb_article_created': 15,
        'quick_resolution': 30,  # Resolveu em < 1h
    }

    def award_points(self, user: User, action: str, extra_points: int = 0):
        """Conceder pontos a um agente"""
        from dashboard.models import AgentLeaderboard
        points = self.POINTS.get(action, 0) + extra_points
        if points <= 0:
            return

        periodo = timezone.now().strftime('%Y-%m')
        lb, created = AgentLeaderboard.objects.get_or_create(
            usuario=user,
            defaults={'periodo': periodo}
        )
        lb.pontos_total += points
        lb.periodo = periodo
        lb.save(update_fields=['pontos_total', 'periodo', 'atualizado_em'])

        # Verificar badges
        self.check_badges(user)

    def check_badges(self, user: User):
        """Verificar e atribuir badges baseado em critérios"""
        from dashboard.models import GamificationBadge, AgentBadge, Ticket

        badges = GamificationBadge.objects.all()
        for badge in badges:
            if AgentBadge.objects.filter(usuario=user, badge=badge).exists():
                continue

            criteria = badge.criteria or {}
            metric = criteria.get('metric')
            threshold = criteria.get('threshold', 0)

            earned = False

            if metric == 'tickets_resolved':
                count = Ticket.objects.filter(
                    agente=user, status__in=['resolvido', 'fechado']
                ).count()
                earned = count >= threshold

            elif metric == 'avg_satisfaction':
                try:
                    from dashboard.models import AvaliacaoSatisfacao
                    avg = AvaliacaoSatisfacao.objects.filter(
                        ticket__agente=user
                    ).aggregate(avg=Avg('nota_atendimento'))['avg']
                    earned = avg and avg >= threshold
                except Exception:
                    pass

            elif metric == 'days_active':
                first_ticket = Ticket.objects.filter(
                    agente=user
                ).order_by('criado_em').first()
                if first_ticket:
                    days = (timezone.now() - first_ticket.criado_em).days
                    earned = days >= threshold

            elif metric == 'quick_resolutions':
                from django.db.models import ExpressionWrapper, DurationField
                count = Ticket.objects.filter(
                    agente=user,
                    status__in=['resolvido', 'fechado'],
                    resolvido_em__isnull=False,
                ).annotate(
                    resolution_time=ExpressionWrapper(
                        F('resolvido_em') - F('criado_em'),
                        output_field=DurationField()
                    )
                ).filter(
                    resolution_time__lt=timedelta(hours=1)
                ).count()
                earned = count >= threshold

            if earned:
                AgentBadge.objects.create(usuario=user, badge=badge)
                self.award_points(user, 'badge_earned', badge.pontos)
                logger.info(f"Badge '{badge.nome}' conquistado por {user.username}")

    def update_leaderboard(self):
        """Atualizar leaderboard de todos os agentes"""
        from dashboard.models import AgentLeaderboard, Ticket

        periodo = timezone.now().strftime('%Y-%m')
        last_30d = timezone.now() - timedelta(days=30)

        agents = User.objects.filter(
            is_staff=True, is_active=True
        )

        for agent in agents:
            tickets = Ticket.objects.filter(agente=agent, criado_em__gte=last_30d)
            resolved = tickets.filter(status__in=['resolvido', 'fechado'])

            lb, created = AgentLeaderboard.objects.get_or_create(
                usuario=agent,
                defaults={'periodo': periodo}
            )

            lb.tickets_resolved = resolved.count()
            lb.periodo = periodo

            # Avg satisfaction
            try:
                from dashboard.models import AvaliacaoSatisfacao
                avg = AvaliacaoSatisfacao.objects.filter(
                    ticket__agente=agent,
                    criado_em__gte=last_30d
                ).aggregate(avg=Avg('nota_atendimento'))['avg']
                lb.avg_satisfaction = round(avg, 2) if avg else 0
            except Exception:
                lb.avg_satisfaction = 0

            # Avg resolution time
            resolved_with_time = resolved.filter(resolvido_em__isnull=False)
            if resolved_with_time.exists():
                avg_delta = resolved_with_time.aggregate(
                    avg=Avg(F('resolvido_em') - F('criado_em'))
                )['avg']
                lb.avg_resolution_hours = round(avg_delta.total_seconds() / 3600, 1) if avg_delta else 0
            else:
                lb.avg_resolution_hours = 0

            lb.save()

        # Atualizar ranks
        all_lb = AgentLeaderboard.objects.order_by('-pontos_total')
        for i, lb in enumerate(all_lb, 1):
            lb.rank = i
            lb.save(update_fields=['rank'])

    def get_leaderboard(self, limit: int = 10) -> list:
        """Retornar top agentes"""
        from dashboard.models import AgentLeaderboard
        return list(
            AgentLeaderboard.objects.select_related('usuario')
            .order_by('-pontos_total')[:limit]
            .values(
                'rank', 'pontos_total', 'tickets_resolved',
                'avg_satisfaction', 'avg_resolution_hours',
                'usuario__username', 'usuario__first_name', 'usuario__last_name',
            )
        )


gamification_service = GamificationService()
