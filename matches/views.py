from django.shortcuts import render

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect

from django.views.generic import DetailView, ListView, TemplateView

from matches.models import Club, Match


# Create your views here.


from operations.mixins import MatchScopedQuerysetMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.generic import TemplateView

from checklists.models import MatchChecklistItem
from matches.models import Match
from matches.utils import combine_match_datetime
from operations.mixins import MatchScopedQuerysetMixin

