# coding=utf-8

import mock
from werkzeug.datastructures import ImmutableOrderedMultiDict, OrderedMultiDict
import pytest

import io

from dmcontent.utils import TemplateField
from dmcontent.content_loader import (
    ContentLoader, ContentSection, ContentManifest, ContentMessage, ContentMetadata,
    read_yaml, ContentNotFoundError, QuestionNotFoundError, _make_slug
)


@pytest.fixture
def manifest_with_sections():
    return ContentManifest([
        {
            "slug": "first_section",
            "name": "First section",
            "editable": False,
            "edit_questions": False,
            "questions": [{
                "id": "q1",
                "question": 'First question',
                "depends": [{
                    "on": "lot",
                    "being": ["SCS", "SaaS", "PaaS"]
                }]
            }]
        },
        {
            "slug": "second_section",
            "name": "Second section",
            "editable": False,
            "edit_questions": False,
            "questions": [{
                "id": "q2",
                "question": 'Second question',
                "depends": [{
                    "on": "lot",
                    "being": ["SCS", "SaaS", "PaaS"]
                }]
            }]
        },
        {
            "slug": "third_section",
            "name": "Third section",
            "editable": True,
            "edit_questions": False,
            "questions": [{
                "id": "q3",
                "question": 'Third question',
                "depends": [{
                    "on": "lot",
                    "being": ["SCS", "SaaS", "PaaS"]
                }]
            }]
        },
        {
            "slug": "fourth_section",
            "name": "Fourth section",
            "editable": False,
            "edit_questions": True,
            "questions": [{
                "id": "q4",
                "question": 'Fourth question',
                "depends": [{
                    "on": "lot",
                    "being": ["SCS", "SaaS", "PaaS"]
                }]
            }]
        },
        {
            "slug": "fifth_section",
            "name": "Fifth section",
            "editable": True,
            "edit_questions": True,
            "questions": [{
                "id": "q5",
                "question": 'Fifth question',
                "depends": [{
                    "on": "lot",
                    "being": ["SCS", "SaaS", "PaaS"]
                }]
            }]
        },
    ])


class TestContentManifest(object):
    def test_content_builder_init(self):
        content = ContentManifest([])

        assert content.sections == []

    def test_content_builder_init_copies_section_list(self):
        sections = []
        content = ContentManifest(sections)

        sections.append('new')
        assert content.sections == []

    def test_content_builder_iteration(self):
        def section(id):
            return {
                'slug': id,
                'name': 'name',
                'questions': []
            }

        content = ContentManifest([section(1), section(2), section(3)])

        assert [s.id for s in content] == [1, 2, 3]

    @pytest.mark.parametrize("filter_inplace_allowed", (False, True,))
    def test_a_question_with_a_dependency(self, filter_inplace_allowed):
        content = ContentManifest([{
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "q1",
                "question": 'First question',
                "depends": [{
                    "on": "lot",
                    "being": ["SCS"]
                }]
            }]
        }]).filter({"lot": "SCS"}, inplace_allowed=filter_inplace_allowed)

        assert len(content.sections) == 1

    @pytest.mark.parametrize("filter_inplace_allowed", (False, True,))
    def test_missing_depends_key_filter(self, filter_inplace_allowed):
        content = ContentManifest([{
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "q1",
                "question": 'First question',
                "depends": [{
                    "on": "lot",
                    "being": ["SCS"]
                }]
            }]
        }]).filter({}, inplace_allowed=filter_inplace_allowed)

        assert len(content.sections) == 0

    @pytest.mark.parametrize("filter_inplace_allowed", (False, True,))
    def test_question_without_dependencies(self, filter_inplace_allowed):
        content = ContentManifest([{
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "q1",
                "question": 'First question',
            }]
        }]).filter({'lot': 'SaaS'}, inplace_allowed=filter_inplace_allowed)

        assert len(content.sections) == 1

    @pytest.mark.parametrize("filter_inplace_allowed", (False, True,))
    def test_a_question_with_a_dependency_that_doesnt_match(self, filter_inplace_allowed):
        content = ContentManifest([{
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "q1",
                "question": 'First question',
                "depends": [{
                    "on": "lot",
                    "being": ["SCS"]
                }]
            }]
        }]).filter({"lot": "SaaS"}, inplace_allowed=filter_inplace_allowed)

        assert len(content.sections) == 0

    @pytest.mark.parametrize("filter_inplace_allowed", (False, True,))
    def test_a_question_which_depends_on_one_of_several_answers(self, filter_inplace_allowed):
        content = ContentManifest([{
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "q1",
                "question": 'First question',
                "depends": [{
                    "on": "lot",
                    "being": ["SCS", "SaaS", "PaaS"]
                }]
            }]
        }])

        assert len(content.filter({"lot": "SaaS"}, inplace_allowed=filter_inplace_allowed).sections) == 1
        assert len(content.filter({"lot": "PaaS"}, inplace_allowed=filter_inplace_allowed).sections) == 1
        assert len(content.filter({"lot": "SCS"}, inplace_allowed=filter_inplace_allowed).sections) == 1

    @pytest.mark.parametrize("filter_inplace_allowed", (False, True,))
    def test_a_question_which_shouldnt_be_shown(self, filter_inplace_allowed):
        content = ContentManifest([{
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "q1",
                "question": 'First question',
                "depends": [{
                    "on": "lot",
                    "being": ["SCS", "SaaS", "PaaS"]
                }]
            }]
        }])

        assert len(content.filter({"lot": "IaaS"}, inplace_allowed=filter_inplace_allowed).sections) == 0

    @pytest.mark.parametrize("filter_inplace_allowed", (False, True,))
    def test_a_section_which_has_a_mixture_of_dependencies(self, filter_inplace_allowed):
        content = ContentManifest([{
            "slug": "first_section",
            "name": "First section",
            "questions": [
                {
                    "id": "q1",
                    "question": 'First question',
                    "depends": [{
                        "on": "lot",
                        "being": ["SCS", "SaaS", "PaaS"]
                    }]
                },
                {
                    "id": "q2",
                    "question": 'Second question',
                    "depends": [{
                        "on": "lot",
                        "being": ["IaaS"]
                    }]
                },
            ]
        }]).filter({"lot": "IaaS"}, inplace_allowed=filter_inplace_allowed)

        assert len(content.sections) == 1

    def test_section_modification(self):
        content = ContentManifest([{
            "slug": "first_section",
            "name": "First section",
            "questions": [
                {
                    "id": "q1",
                    "question": 'First question',
                    "depends": [{
                        "on": "lot",
                        "being": ["SCS", "SaaS", "PaaS"]
                    }]
                },
                {
                    "id": "q2",
                    "question": 'Second question',
                    "depends": [{
                        "on": "lot",
                        "being": ["IaaS"]
                    }]
                },
            ]
        }])

        content2 = content.filter({"lot": "IaaS"})

        assert len(content.sections[0]["questions"]) == 2
        assert len(content2.sections[0]["questions"]) == 1

    @pytest.mark.parametrize("filter_inplace_allowed", (False, True,))
    def test_that_filtering_is_cumulative(self, filter_inplace_allowed):
        content = ContentManifest([{
            "slug": "first_section",
            "name": "First section",
            "questions": [
                {
                    "id": "q1",
                    "question": 'First question',
                    "depends": [{
                        "on": "lot",
                        "being": ["SCS", "SaaS", "PaaS"]
                    }]
                },
                {
                    "id": "q2",
                    "question": 'Second question',
                    "depends": [{
                        "on": "lot",
                        "being": ["SCS", "IaaS"]
                    }]
                },
                {
                    "id": "q3",
                    "question": 'Third question',
                    "depends": [{
                        "on": "lot",
                        "being": ["SaaS", "IaaS"]
                    }]
                },
            ]
        }])

        content = content.filter({"lot": "SCS"}, inplace_allowed=filter_inplace_allowed)
        assert len(content.sections[0]["questions"]) == 2

        content = content.filter({"lot": "IaaS"}, inplace_allowed=filter_inplace_allowed)
        assert len(content.sections[0]["questions"]) == 1

        content = content.filter({"lot": "PaaS"}, inplace_allowed=filter_inplace_allowed)
        assert len(content.sections) == 0

    @pytest.mark.parametrize("filter_inplace_allowed", (False, True,))
    def test_get_section(self, filter_inplace_allowed):
        content = ContentManifest([{
            "slug": "first_section",
            "name": "First section",
            "questions": [
                {
                    "id": "q1",
                    "question": 'First question',
                    "depends": [{
                        "on": "lot",
                        "being": ["SCS", "SaaS", "PaaS"]
                    }]
                }
            ]
        }])

        assert content.get_section("first_section").id == "first_section"

        content = content.filter({"lot": "IaaS"}, inplace_allowed=filter_inplace_allowed)
        assert content.get_section("first_section") is None

    @pytest.mark.parametrize("summary_inplace_allowed", (False, True,))
    def test_summary(self, summary_inplace_allowed):
        content = ContentManifest([{
            "slug": "first_section",
            "name": "First section",
            "questions": [
                {
                    "id": "q1",
                    "question": 'First question',
                    "type": "multiquestion",
                    "questions": [
                        {"id": "q2", "type": "text"},
                        {"id": "q3", "type": "text"},
                        {"id": "q12", "type": "boolean", "followup": {"q13": [True], "q14": [True]}},
                        {"id": "q13", "type": "text"},
                        {"id": "q14", "type": "text", "optional": True}
                    ]
                },
                {"id": "q4", "type": "text", "optional": True},
                {"id": "q5", "type": "text", "optional": False},
                {"id": "q6", "type": "text", "optional": False},
                {
                    "id": "q7",
                    "type": "pricing",
                    "fields": {
                        "minimum_price": "q7.min",
                        "maximum_price": "q7.max",
                        "price_unit": "q7.unit",
                    },
                    "optional_fields": [
                        "maximum_price"
                    ]
                },
                {
                    "id": "q8",
                    "type": "pricing",
                    "fields": {
                        "minimum_price": "q8.min",
                        "maximum_price": "q8.max",
                    },
                    "optional_fields": [
                        "maximum_price"
                    ]
                },
                {
                    "id": "q9",
                    "question": 'Never required question',
                    "optional": True,
                    "questions": [
                        {"id": "q71", "type": "text"},
                        {"id": "q72", "type": "text"}
                    ]
                },
                {
                    "id": "q10",
                    "question": 'Are you sure you are assured?',
                    'type': 'boolean',
                    "optional": False,
                    'assuranceApproach': '2answers-type1',
                }
            ]
        }])

        summary = content.summary({
            'q2': 'some value',
            'q6': 'another value',
            'q7.min': '10',
            'q7.unit': 'day',
            'q10': {'value': True, 'assurance': 'Service provider assertion'},
            'q11': {'value': True}
        }, inplace_allowed=summary_inplace_allowed)

        assert summary.get_question('q1').value == [
            summary.get_question('q2')
        ]
        assert summary.get_question('q1').answer_required
        assert summary.get_question('q2').value == 'some value'
        assert not summary.get_question('q2').answer_required
        assert summary.get_question('q3').answer_required
        assert summary.get_question('q4').value == ''
        assert not summary.get_question('q4').answer_required
        assert summary.get_question('q4').assurance == ''  # question without assurance returns an empty string
        assert summary.get_question('q5').answer_required
        assert not summary.get_question('q6').answer_required
        assert summary.get_question('q7').value == u'£10 a day'
        assert not summary.get_question('q7').answer_required
        assert summary.get_question('q8').answer_required
        assert not summary.get_question('q9').answer_required
        assert summary.get_question('q10').value is True
        assert summary.get_question('q10').assurance == 'Service provider assertion'

        assert summary.get_question('q12').answer_required
        assert summary.get_question('q13').answer_required
        assert not summary.get_question('q14').answer_required

    @pytest.mark.parametrize("filter_inplace_allowed", (False, True,))
    def test_get_question(self, filter_inplace_allowed):
        content = ContentManifest([
            {
                "slug": "first_section",
                "name": "First section",
                "questions": [{
                    "id": "q1",
                    "question": 'First question',
                    "depends": [{
                        "on": "lot",
                        "being": ["SCS", "SaaS", "PaaS"]
                    }]
                }]
            },
            {
                "slug": "second_section",
                "name": "Second section",
                "questions": [{
                    "id": "q2",
                    "question": 'First question',
                    "depends": [{
                        "on": "lot",
                        "being": ["SCS", "SaaS", "PaaS"]
                    }]
                }]
            },
            {
                "slug": "third_section",
                "name": "Third section",
                "editable": True,
                "questions": [{
                    "id": "q3",
                    "question": 'First question',
                    "depends": [{
                        "on": "lot",
                        "being": ["SCS", "SaaS", "PaaS"]
                    }]
                }]
            },
        ])

        assert content.get_question('q1').get('id') == 'q1'

        content = content.filter({'lot': 'IaaS'}, inplace_allowed=filter_inplace_allowed)
        assert content.get_question('q1') is None

    def test_get_question_by_slug(self):
        content = ContentManifest([
            {
                "slug": "first_section",
                "name": "First section",
                "questions": [{
                    "id": "q1",
                    "type": "multiquestion",
                    "question": 'Section one question',
                    "slug": "section-one-question",
                    "questions": [{"id": "sec1One"}, {"id": "sec1Two"}],
                    "depends": [{
                        "on": "lot",
                        "being": ["digital-specialists"]
                    }]
                }]
            },
            {
                "slug": "second_section",
                "name": "Second section",
                "questions": [{
                    "id": "q2",
                    "type": "multiquestion",
                    "question": 'Section two question',
                    "slug": "section-two-question",
                    "questions": [{"id": "sec2One"}, {"id": "sec2Two"}],
                    "depends": [{
                        "on": "lot",
                        "being": ["digital-specialists"]
                    }]
                }]
            }
        ])

        assert content.get_question_by_slug('section-two-question').get('id') == 'q2'

    def test_get_next_section(self, manifest_with_sections):
        assert manifest_with_sections.get_next_section_id() == "first_section"
        assert manifest_with_sections.get_next_section_id("first_section") == "second_section"
        assert manifest_with_sections.get_next_section_id("second_section") == "third_section"
        assert manifest_with_sections.get_next_section_id("third_section") == "fourth_section"
        assert manifest_with_sections.get_next_section_id("fourth_section") == "fifth_section"
        assert manifest_with_sections.get_next_section_id("fifth_section") is None

    def test_get_next_editable_section(self, manifest_with_sections):
        assert manifest_with_sections.get_next_editable_section_id() == "third_section"
        assert manifest_with_sections.get_next_editable_section_id("first_section") == "third_section"
        assert manifest_with_sections.get_next_editable_section_id("second_section") == "third_section"
        assert manifest_with_sections.get_next_editable_section_id("third_section") == "fifth_section"
        assert manifest_with_sections.get_next_editable_section_id("fourth_section") == "fifth_section"
        assert manifest_with_sections.get_next_editable_section_id("fifth_section") is None

    def test_get_next_edit_questions_section(self, manifest_with_sections):
        assert manifest_with_sections.get_next_edit_questions_section_id() == "fourth_section"
        assert manifest_with_sections.get_next_edit_questions_section_id("first_section") == "fourth_section"
        assert manifest_with_sections.get_next_edit_questions_section_id("second_section") == "fourth_section"
        assert manifest_with_sections.get_next_edit_questions_section_id("third_section") == "fourth_section"
        assert manifest_with_sections.get_next_edit_questions_section_id("fourth_section") == "fifth_section"
        assert manifest_with_sections.get_next_edit_questions_section_id("fifth_section") is None

    def test_get_all_data(self):
        content = ContentManifest([
            {
                "slug": "first_section",
                "name": "First section",
                "questions": [{
                    "id": "q1",
                    "question": "Question one",
                    "type": "text",
                }]
            },
            {
                "slug": "second_section",
                "name": "Second section",
                "questions": [{
                    "id": "q2",
                    "question": "Question two",
                    "type": "text",
                }]
            },
            {
                "slug": "third_section",
                "name": "Third section",
                "questions": [{
                    "id": "q3",
                    "question": "Question three",
                    "type": "text",
                }]
            }
        ])

        form = ImmutableOrderedMultiDict([
            ('q1', 'some text'),
            ('q2', 'other text'),
            ('q3', '  lots of      whitespace     \t\n'),
        ])

        data = content.get_all_data(form)

        assert data == {
            'q1': 'some text',
            'q2': 'other text',
            'q3': 'lots of      whitespace',
        }

    def test_question_numbering(self):
        content = ContentManifest([
            {
                "slug": "first_section",
                "name": "First section",
                "questions": [
                    {
                        "id": "q1",
                        "question": "Question one",
                        "type": "text",
                    },
                    {
                        "id": "q2",
                        "question": "Question one",
                        "type": "text",
                    }
                ]
            },
            {
                "slug": "second_section",
                "name": "Second section",
                "questions": [
                    {
                        "id": "q3",
                        "question": "Question three",
                        "type": "text",
                    }
                ]
            }
        ])

        assert content.get_question("q1")['number'] == 1
        assert content.get_question("q2")['number'] == 2
        assert content.get_question("q3")['number'] == 3

    @pytest.mark.parametrize("filter_inplace_allowed", (False, True,))
    def test_question_numbers_respect_filtering(self, filter_inplace_allowed):
        content = ContentManifest([
            {
                "slug": "first_section",
                "name": "First section",
                "questions": [{
                    "id": "q1",
                    "question": 'First question',
                    "depends": [{
                        "on": "lot",
                        "being": ["SaaS"]
                    }]
                }]
            },
            {
                "slug": "second_section",
                "name": "Second section",
                "questions": [
                    {
                        "id": "q2",
                        "question": 'Second question',
                        "depends": [{
                            "on": "lot",
                            "being": ["SCS"]
                        }]
                    },
                    {
                        "id": "q3",
                        "question": 'Third question',
                        "depends": [{
                            "on": "lot",
                            "being": ["SCS"]
                        }]
                    },
                ]
            }
        ]).filter({"lot": "SCS"}, inplace_allowed=filter_inplace_allowed)

        assert content.sections[0].questions[0]['id'] == 'q2'
        assert content.get_question('q2')['number'] == 1
        assert content.sections[0].questions[0]['number'] == 1


class TestContentSection(object):
    def setup_for_boolean_list_tests(self):
        section = {
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "q0",
                "question": "Boolean list question",
                "type": "boolean_list",
            }]
        }

        brief = {
            "briefs": {
                "id": "0",
                "q0": [
                    "Can you do Sketch, Photoshop, Illustrator, and InDesign?",
                    "Can you can communicate like a boss?",
                    "Can you write clean and semantic HTML, CSS and Javascript?",
                    "Can you fight injustice full time?"
                ]
            }
        }

        form = OrderedMultiDict([
            ('q0-0', 'true'),
            ('q0-1', 'true'),
            ('q0-2', 'true'),
            ('q0-3', 'true')
        ])

        return section, brief, form

    def test_has_summary_page_if_multiple_questions(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "prefill": False,
            "questions": [{
                "id": "q1",
                "question": "Boolean question",
                "type": "boolean",
            }, {
                "id": "q2",
                "question": "Text question",
                "type": "text",
            }]
        })
        assert section.has_summary_page is True

    @pytest.mark.parametrize("filter_inplace_allowed", (False, True,))
    def test_has_no_summary_page_if_single_question_no_description(self, filter_inplace_allowed):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "q1",
                "question": "Boolean question",
                "type": "boolean",
            }]
        }).filter({}, inplace_allowed=filter_inplace_allowed)
        assert section.has_summary_page is False

    @pytest.mark.parametrize("filter_inplace_allowed", (False, True,))
    def test_has_summary_page_if_single_question_with_description(self, filter_inplace_allowed):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "description": "Section about a single topic",
            "questions": [{
                "id": "q1",
                "question": "Boolean question",
                "type": "boolean",
            }]
        }).filter({}, inplace_allowed=filter_inplace_allowed)
        assert section.has_summary_page is True

    def test_get_question_ids(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "q1",
                "question": "Boolean question",
                "type": "boolean",
            }, {
                "id": "q2",
                "question": "Text question",
                "type": "text",
            }]
        })
        assert section.get_question_ids() == ['q1', 'q2']

    def test_get_multiquestion_ids(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "q0",
                "question": "Boolean question",
                "type": "multiquestion",
                "questions": [
                    {
                        "id": "q2",
                        "type": "text"
                    },
                    {
                        "id": "q3",
                        "type": "text"
                    }
                ]
            }]
        })
        assert section.get_question_ids() == ['q2', 'q3']

    def test_get_next_question_id(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "first_question",
                "question": "Boolean question",
                "type": "boolean",
            }, {
                "id": "second_question",
                "question": "Multi question",
                "type": "multiquestion",
                "questions": [
                    {
                        "id": "multiquestion-1",
                        "type": "text"
                    },
                    {
                        "id": "multiquestion-2",
                        "type": "text"
                    }
                ]
            }, {
                "id": "third_question",
                "question": "Text question",
                "type": "text",
            }]
        })

        assert section.get_next_question_id() == "first_question"
        assert section.get_next_question_id("first_question") == "second_question"
        assert section.get_next_question_id("second_question") == "third_question"
        assert section.get_next_question_id("third_question") is None

    def test_get_next_question_id_for_section_with_no_questions_returns_none(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": []
        })
        assert section.get_next_question_id() is None

    def test_get_previous_question_id(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "first_question",
                "question": "Boolean question",
                "type": "boolean",
            }, {
                "id": "second_question",
                "question": "Multi question",
                "type": "multiquestion",
                "questions": [
                    {
                        "id": "multiquestion-1",
                        "type": "text"
                    },
                    {
                        "id": "multiquestion-2",
                        "type": "text"
                    }
                ]
            }, {
                "id": "third_question",
                "question": "Text question",
                "type": "text",
            }]
        })

        assert section.get_previous_question_id("first_question") is None
        assert section.get_previous_question_id("second_question") == "first_question"
        assert section.get_previous_question_id("third_question") == "second_question"
        assert section.get_previous_question_id("does_not_exist") is None
        assert section.get_previous_question_id(None) is None

    def test_get_previous_question_id_for_section_with_no_questions_returns_none(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": []
        })
        assert section.get_previous_question_id(None) is None

    def test_get_next_question_slug(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "first_question",
                "slug": "first_question_slug",
                "question": "Boolean question",
                "type": "boolean",
            }, {
                "id": "second_question",
                "slug": "second_question_slug",
                "question": "Multi question",
                "type": "multiquestion",
                "questions": [
                    {
                        "id": "multiquestion-1",
                        "slug": "multiquestion_1_slug",
                        "type": "text"
                    },
                    {
                        "id": "multiquestion-2",
                        "slug": "multiquestion_2_slug",
                        "type": "text"
                    }
                ]
            }, {
                "id": "third_question",
                "slug": "third_question_slug",
                "question": "Text question",
                "type": "text",
            }]
        })

        assert section.get_next_question_slug() == "first_question_slug"
        assert section.get_next_question_slug("first_question_slug") == "second_question_slug"
        assert section.get_next_question_slug("second_question_slug") == "third_question_slug"
        assert section.get_next_question_slug("third_question_slug") is None

    def test_get_next_question_slug_for_section_with_no_questions_returns_none(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": []
        })
        assert section.get_next_question_slug() is None

    def test_get_previous_question_slug(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "prefill": False,
            "questions": [{
                "id": "first_question",
                "slug": "first_question_slug",
                "question": "Boolean question",
                "type": "boolean",
            }, {
                "id": "second_question",
                "slug": "second_question_slug",
                "question": "Multi question",
                "type": "multiquestion",
                "questions": [
                    {
                        "id": "multiquestion-1",
                        "slug": "multiquestion_1_slug",
                        "type": "text"
                    },
                    {
                        "id": "multiquestion-2",
                        "slug": "multiquestion_2_slug",
                        "type": "text"
                    }
                ]
            }, {
                "id": "third_question",
                "slug": "third_question_slug",
                "question": "Text question",
                "type": "text",
            }]
        })

        assert section.get_previous_question_slug("first_question_slug") is None
        assert section.get_previous_question_slug("second_question_slug") == "first_question_slug"
        assert section.get_previous_question_slug("third_question_slug") == "second_question_slug"
        assert section.get_previous_question_slug("does_not_exist") is None
        assert section.get_previous_question_slug(None) is None

    def test_get_previous_question_slug_for_section_with_no_questions_returns_none(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": []
        })
        assert section.get_previous_question_slug(None) is None

    @pytest.mark.parametrize("filter_inplace_allowed", (False, True,))
    def test_get_multiquestion_as_section(self, filter_inplace_allowed):
        section = ContentSection.create({
            "slug": "first_section",
            "prefill": True,
            "edit_questions": True,
            "editable": True,
            "name": "First section",
            "questions": [{
                "id": "q0",
                "slug": "q0-slug",
                "question": "Q0",
                "type": "multiquestion",
                "hint": "Some description",
                "questions": [
                    {
                        "id": "q2",
                        "type": "text"
                    },
                    {
                        "id": "q3",
                        "type": "text"
                    }
                ]
            }]
        }).filter({}, inplace_allowed=filter_inplace_allowed)

        question_section = section.get_question_as_section('q0-slug')
        assert question_section.name == "Q0"
        assert question_section.description == "Some description"
        assert question_section.prefill is True
        assert question_section.editable == section.edit_questions
        assert question_section.get_question_ids() == ['q2', 'q3']

    @pytest.mark.parametrize("filter_inplace_allowed", (False, True,))
    def test_get_non_multiquestion_question_as_section(self, filter_inplace_allowed):
        section = ContentSection.create({
            "slug": "first_section",
            "edit_questions": True,
            "name": "First section",
            "questions": [{"id": "q1", "type": "text", "slug": "q1-slug", "question": "Q1", "hint": "Some description"},
                          {"id": "q2", "type": "text", "slug": "q2-slug", "question": "Q2", "hint": "Some description"}]
        }).filter({}, inplace_allowed=filter_inplace_allowed)

        question_section = section.get_question_as_section('q1-slug')
        assert question_section.slug == "q1-slug"
        assert question_section.description == ""
        assert question_section.prefill is None
        assert question_section.editable == section.edit_questions
        assert question_section.edit_questions is False

    def test_get_question_as_section_missing_question(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "q0",
                "question": "Q0",
            }]
        })

        question_section = section.get_question_as_section('q0-slug')
        assert question_section is None

    def test_get_question_ids_filtered_by_type(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "q1",
                "question": "Boolean question",
                "type": "boolean",
            }, {
                "id": "q2",
                "question": "Text question",
                "type": "text",
            }]
        })
        assert section.get_question_ids('boolean') == ['q1']

    def test_get_data(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "q0",
                "type": "multiquestion",
                "questions": [
                    {"id": "q01", "type": "text"},
                    {"id": "q02", "type": "radios"}
                ]
            }, {
                "id": "q1",
                "question": "Boolean question",
                "type": "boolean",
            }, {
                "id": "q2",
                "question": "Text question",
                "type": "text",
            }, {
                "id": "q3",
                "question": "Radios question",
                "type": "radios",
            }, {
                "id": "q4",
                "question": "List question",
                "type": "list",
            }, {
                "id": "q5",
                "question": "Boolean list question",
                "type": "boolean_list",
            }, {
                "id": "q6",
                "question": "Checkboxes question",
                "type": "checkboxes",
            }, {
                "id": "q7",
                "question": "Service ID question",
                "type": "service_id",
                "assuranceApproach": "2answers-type1",
            }, {
                "id": "q8",
                "question": "Pricing question",
                "type": "pricing",
                "fields": {
                    "minimum_price": "q8-min_price",
                    "maximum_price": "q8-max_price",
                    "price_unit": "q8-price_unit",
                    "price_interval": "q8-price_interval"
                }
            }, {
                "id": "q9",
                "question": "Upload question",
                "type": "upload",
            }, {
                "id": "q10",
                "question": "number question",
                "type": "number",
            }, {
                "id": "q101",
                "question": "zero number question",
                "type": "number",
            }, {
                "id": "q11",
                "question": "Large text question",
                "type": "textbox_large",
            }, {
                "id": "q12",
                "question": "Text question",
                "type": "text"
            }, {
                "id": "q13",
                "question": "Text question",
                "type": "text"
            }]
        })

        form = ImmutableOrderedMultiDict([
            ('q1', 'true'),
            ('q01', 'some nested question'),
            ('q2', 'Some text stuff'),
            ('q3', 'value'),
            ('q3', 'Should be lost'),
            ('q4', 'value 1'),
            ('q4', 'value 2'),
            ('q5-0', 'true'),
            ('q5-1', 'false'),
            ('q5-4', 'true'),
            ('q5-not-valid', 'true'),
            ('q6', 'check 1'),
            ('q6', 'check 2'),
            ('q7', '71234567890'),
            ('q7--assurance', 'yes I am'),
            ('q8-min_price', '12.12'),
            ('q8-max_price', ''),
            ('q8-price_unit', 'Unit'),
            ('q8-price_interval', 'Hour'),
            ('q9', 'blah blah'),
            ('q10', '12.12'),
            ('q101', '0'),
            ('q11', 'Looooooooaaaaaaaaads of text'),
            ('extra_field', 'Should be lost'),
            ('q13', ''),
        ])

        data = section.get_data(form)

        assert data == {
            'q01': 'some nested question',
            'q1': True,
            'q2': 'Some text stuff',
            'q3': 'value',
            'q4': ['value 1', 'value 2'],
            'q5': [True, False, None, None, True],
            'q6': ['check 1', 'check 2'],
            'q7': {'assurance': 'yes I am', 'value': '71234567890'},
            'q8-min_price': '12.12',
            'q8-max_price': None,
            'q8-price_unit': 'Unit',
            'q8-price_interval': 'Hour',
            'q10': 12.12,
            'q101': 0,
            'q11': 'Looooooooaaaaaaaaads of text',
            'q13': None,
        }

        # Failure modes
        form = ImmutableOrderedMultiDict([
            ('q1', 'not boolean')
        ])
        assert section.get_data(form)['q1'] == 'not boolean'

        form = ImmutableOrderedMultiDict([
            ('q1', 'false')
        ])
        assert section.get_data(form)['q1'] is False

        form = ImmutableOrderedMultiDict([
            ('q10', 'not a number')
        ])
        assert section.get_data(form)['q10'] == 'not a number'

        # Test 'orphaned' assurance is returned
        form = ImmutableOrderedMultiDict([
            ('q7--assurance', 'yes I am'),
        ])
        data = section.get_data(form)
        assert data == {
            'q4': None,
            'q6': None,
            'q7': {'assurance': 'yes I am'},
        }

        # Test empty lists are not converted to `None`
        form = ImmutableOrderedMultiDict([
            ('q4', '')
        ])
        assert section.get_data(form)['q4'] == ['']

        # if we have one empty value
        form = ImmutableOrderedMultiDict([
            ('q5-0', '')
        ])
        assert section.get_data(form)['q5'] == ['']

        # if we have a value without an index number, we ignore it
        form = ImmutableOrderedMultiDict([
            ('q5', 'true'),
            ('q5-', 'true')
        ])
        assert 'q5' not in section.get_data(form)

    def test_unformat_data(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "q0",
                "questions": [
                    {"id": "q01", "type": "text"},
                    {"id": "q02", "type": "radios"}
                ]
            }, {
                "id": "q1",
                "question": "Boolean question",
                "type": "boolean",
            }, {
                "id": "q2",
                "question": "Text question",
                "type": "text",
            }, {
                "id": "q3",
                "question": "Radios question",
                "type": "radios",
            }, {
                "id": "q4",
                "question": "List question",
                "type": "list",
            }, {
                "id": "q5",
                "question": "Boolean list question",
                "type": "boolean_list",
            }, {
                "id": "q6",
                "question": "Checkboxes question",
                "type": "checkboxes",
            }, {
                "id": "q7",
                "question": "Service ID question",
                "type": "service_id",
                "assuranceApproach": "2answers-type1",
            }, {
                "id": "q8",
                "question": "Pricing question",
                "type": "pricing",
                "fields": {
                    "minimim_price": "q8-min",
                    "maximum_price": "q8-min",
                    "price_unit": "q8-unit",
                    "price_interval": "q8-interval"
                }
            }, {
                "id": "q9",
                "question": "Upload question",
                "type": "upload",
            }, {
                "id": "q10",
                "question": "number question",
                "type": "number",
            }, {
                "id": "q11",
                "question": "Large text question",
                "type": "textbox_large",
            }, {
                "id": "q12",
                "question": "Text question",
                "type": "text"
            }]
        })

        data = {
            'q01': 'q01 value',
            'q1': True,
            'q2': 'Some text stuff',
            'q3': 'value',
            'q4': ['value 1', 'value 2'],
            'q5': [True, False],
            'q6': ['check 1', 'check 2'],
            'q7': {'assurance': 'yes I am', 'value': '71234567890'},
            'q8-min': '12.12',
            'q8-max': '13.13',
            'q8-unit': 'Unit',
            'q8-interval': 'Hour',
            'q10': 12.12,
            'q11': 'Looooooooaaaaaaaaads of text',
        }

        form = section.unformat_data(data)

        assert form == {
            'q01': 'q01 value',
            'q1': True,
            'q2': 'Some text stuff',
            'q3': 'value',
            'q4': ['value 1', 'value 2'],
            'q5': [True, False],
            'q6': ['check 1', 'check 2'],
            'q7': '71234567890',
            'q7--assurance': 'yes I am',
            'q8-min': '12.12',
            'q8-max': '13.13',
            'q8-unit': 'Unit',
            'q8-interval': 'Hour',
            'q10': 12.12,
            'q11': 'Looooooooaaaaaaaaads of text',
        }

    def test_get_question(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "q1",
                "question": 'First question',
                "depends": [{
                    "on": "lot",
                    "being": ["SCS", "SaaS", "PaaS"]
                }]
            }]
        })

        assert section.get_question('q1').get('id') == 'q1'

    def test_get_field_names_with_incomplete_pricing_question(self):
        with pytest.raises(KeyError):
            section = ContentSection.create({
                "slug": "first_section",
                "name": "First section",
                "questions": [{
                    "id": "q1",
                    "question": "First question",
                    "type": "pricing",
                }]
            })
            section.get_field_names()

    def test_get_field_names_with_good_pricing_question(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": [{
                "id": "q1",
                "question": "First question",
                "type": "pricing",
                "fields": {
                    "minimum_price": "q1-minprice",
                    "maximum_price": "q1-maxprice"
                }
            }]
        })

        # using sets because sort order -TM
        expected = set(['q1-minprice', 'q1-maxprice'])
        assert set(section.get_field_names()) == expected

    def test_get_field_names_with_no_pricing_question(self):
        section = ContentSection.create({
            "slug": "second_section",
            "name": "Second section",
            "questions": [{
                "id": "q2",
                "question": "Second question",
                "type": "text",
            }]
        })

        assert section.get_field_names() == ['q2']

    def test_has_changes_to_save_no_changes(self):
        section = ContentSection.create({
            "slug": "second_section",
            "name": "Second section",
            "questions": [{
                "id": "q2",
                "question": "Second question",
                "type": "text",
            }]
        })
        assert not section.has_changes_to_save({'q2': 'foo'}, {'q2': 'foo'})

    def test_hash_changes_to_save_field_different(self):
        section = ContentSection.create({
            "slug": "second_section",
            "name": "Second section",
            "questions": [{
                "id": "q2",
                "question": "Second question",
                "type": "text",
            }]
        })
        assert section.has_changes_to_save({'q2': 'foo'}, {'q2': 'blah'})

    def test_has_changes_to_save_field_not_set_on_service(self):
        section = ContentSection.create({
            "slug": "second_section",
            "name": "Second section",
            "questions": [{
                "id": "q2",
                "question": "Second question",
                "type": "text",
            }]
        })
        assert section.has_changes_to_save({}, {})

    def test_get_error_message(self):
        section = ContentSection.create({
            "slug": "second_section",
            "name": "Second section",
            "questions": [{
                "id": "q2",
                "question": "Second question",
                "type": "text",
                "validations": [
                    {'name': 'the_error', 'message': 'This is the error message'},
                ],
            }]
        })

        expected = "This is the error message"
        assert section.get_question('q2').get_error_message('the_error') == expected

    def test_get_error_message_returns_default(self):
        section = ContentSection.create({
            "slug": "second_section",
            "name": "Second section",
            "questions": [{
                "id": "q2",
                "question": "Second question",
                "type": "text",
                "validations": [
                    {'name': 'the_error', 'message': 'This is the error message'},
                ],
            }]
        })

        expected = "There was a problem with the answer to this question."
        assert section.get_question('q2').get_error_message('other_error') == expected

    @pytest.mark.parametrize("question_descriptor_from", ("label", "question",))
    def test_get_error_messages(self, question_descriptor_from):
        section = ContentSection.create({
            "slug": "second_section",
            "name": "Second section",
            "prefill": True,
            "questions": [{
                "id": "q2",
                "question": "Second question",
                "name": "second",
                "type": "text",
                "validations": [
                    {'name': 'the_error', 'message': 'This is the error message'},
                ],
            }, {
                "id": "serviceTypes",
                "question": "Third question",
                "type": "text",
                "validations": [
                    {'name': 'the_error', 'message': 'This is the error message'},
                ],
            }, {
                "id": "priceString",
                "question": "Price question",
                "type": "pricing",
                "fields": {
                    "minimum_price": "priceString-min"
                },
                "validations": [
                    {
                        "name": "answer_required",
                        "field": "priceString-min",
                        "message": "No min price"
                    },
                ]
            }, {
                "id": "q3",
                "question": "With assurance",
                "type": "text",
                "validations": [
                    {"name": "assurance_required", "message": "There there, it'll be ok."},
                ]
            }, {
                "id": "q4",
                "question": "No Errors",
                "type": "text"
            }]
        })

        errors = {
            "q2": "the_error",
            "q3": "assurance_required",
            "serviceTypes": "the_error",
            "priceString-min": "answer_required",
        }

        result = section.get_error_messages(errors, question_descriptor_from=question_descriptor_from)

        assert result['priceString']['message'] == "No min price"
        assert result['q2']['message'] == "This is the error message"
        assert result['q2']['question'] == "Second question" if question_descriptor_from == "question" else "second"
        assert result['q3--assurance']['message'] == "There there, it'll be ok."
        assert result['serviceTypes']['message'] == "This is the error message"

        assert result["priceString"]["input_name"] == "priceString"

        assert list(result.keys()) == ["q2", "serviceTypes", "priceString", "q3--assurance"]

    def test_get_error_messages_with_unknown_error_key(self):
        section = ContentSection.create({
            "slug": "second_section",
            "name": "Second section",
            "questions": []
        })
        errors = {
            "q1": "the_error"
        }

        with pytest.raises(QuestionNotFoundError):
            section.get_error_messages(errors)

    @pytest.mark.parametrize("summary_inplace_allowed", (False, True,))
    def test_get_error_messages_for_boolean_list_one_question_missing(self, summary_inplace_allowed):

        section, brief, form_data = self.setup_for_boolean_list_tests()
        form_data.pop('q0-3')
        errors = {"q0": "boolean_list_error"}

        section = ContentSection.create(section)
        section.inject_brief_questions_into_boolean_list_question(brief['briefs'])
        response_data = section.get_data(form_data)
        section_summary = section.summary(response_data, inplace_allowed=summary_inplace_allowed)
        error_messages = section_summary.get_error_messages(errors)

        assert error_messages['q0'] is True
        for error_key in ['q0-3']:
            assert error_key in error_messages
            base_error_key, index = error_key.split('-')[0], int(error_key.split('-')[-1])
            assert brief['briefs'][base_error_key][index] == error_messages[error_key]['question']

    @pytest.mark.parametrize("summary_inplace_allowed", (False, True,))
    def test_get_error_messages_for_boolean_list_all_questions_missing(self, summary_inplace_allowed):

        section, brief, form_data = self.setup_for_boolean_list_tests()
        form_data.pop('q0-0')
        form_data.pop('q0-1')
        form_data.pop('q0-2')
        form_data.pop('q0-3')
        errors = {"q0": "boolean_list_error"}

        section = ContentSection.create(section)
        section.inject_brief_questions_into_boolean_list_question(brief['briefs'])
        response_data = section.get_data(form_data)
        section_summary = section.summary(response_data, inplace_allowed=summary_inplace_allowed)
        error_messages = section_summary.get_error_messages(errors)

        assert error_messages['q0'] is True
        for error_key in ['q0-0', 'q0-1', 'q0-2', 'q0-3']:
            assert error_key in error_messages
            base_error_key, index = error_key.split('-')[0], int(error_key.split('-')[-1])
            assert brief['briefs'][base_error_key][index] == error_messages[error_key]['question']

    @pytest.mark.parametrize("summary_inplace_allowed", (False, True,))
    def test_get_error_messages_no_boolean_list_questions_missing(self, summary_inplace_allowed):

        section, brief, form_data = self.setup_for_boolean_list_tests()
        section['questions'].append({
            "id": "q1",
            "question": "Text question",
            "type": "text"
        })
        errors = {"q1": "text_error"}

        section = ContentSection.create(section)
        section.inject_brief_questions_into_boolean_list_question(brief['briefs'])
        response_data = section.get_data(form_data)
        section_summary = section.summary(response_data, inplace_allowed=summary_inplace_allowed)
        error_messages = section_summary.get_error_messages(errors)

        assert 'q1' in error_messages
        for error_key in ['q0', 'q0-0', 'q0-1', 'q0-2', 'q0-3']:
            assert error_key not in error_messages

    def test_cannot_get_boolean_list_error_messages_without_section_summary(self):

        section, brief, form_data = self.setup_for_boolean_list_tests()
        form_data.pop('q0-3')
        errors = {"q0": "boolean_list_error"}

        section = ContentSection.create(section)
        section.inject_brief_questions_into_boolean_list_question(brief['briefs'])
        error_messages = section.get_error_messages(errors)

        assert 'q0' in error_messages
        assert 'q0-3' not in error_messages
        assert len(error_messages.keys()) == 1

    @pytest.mark.parametrize("summary_inplace_allowed", (False, True,))
    def test_get_wrong_boolean_list_error_messages_without_brief_questions_injected(self, summary_inplace_allowed):

        section, brief, form_data = self.setup_for_boolean_list_tests()
        form_data.pop('q0-3')
        errors = {"q0": "boolean_list_error"}

        section = ContentSection.create(section)
        response_data = section.get_data(form_data)
        section_summary = section.summary(response_data, inplace_allowed=summary_inplace_allowed)
        error_messages = section_summary.get_error_messages(errors)

        assert 'q0' in error_messages
        assert 'q0-3' not in error_messages
        assert len(error_messages.keys()) == 1

    @pytest.mark.parametrize("summary_inplace_allowed", (False, True,))
    def test_get_wrong_boolean_list_error_messages_without_response_data(self, summary_inplace_allowed):

        section, brief, form_data = self.setup_for_boolean_list_tests()
        form_data.pop('q0-3')
        errors = {"q0": "boolean_list_error"}

        section = ContentSection.create(section)
        section.inject_brief_questions_into_boolean_list_question(brief['briefs'])
        section_summary = section.summary({}, inplace_allowed=summary_inplace_allowed)
        error_messages = section_summary.get_error_messages(errors)

        # when an error key exists but no response data, all questions are assumed empty
        for error_key in ['q0', 'q0-0', 'q0-1', 'q0-2', 'q0-3']:
            assert error_key in error_messages

    @pytest.mark.parametrize("filter_inplace_allowed", (False, True,))
    def test_section_description(self, filter_inplace_allowed):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": [{"id": "q1", "question": "Why?", "type": "text"}],
            "description": "This is the first section",
            "summary_page_description": "This is a summary of the first section"
        }).filter({}, inplace_allowed=filter_inplace_allowed)
        assert section.description == "This is the first section"
        assert section.summary_page_description == "This is a summary of the first section"

        copy_of_section = section.copy()
        assert copy_of_section.description == "This is the first section"
        assert copy_of_section.summary_page_description == "This is a summary of the first section"

    def test_section_step(self):
        section = ContentSection.create({
            "slug": "first_section",
            "name": "First section",
            "questions": [],
            "step": 1
        })
        assert section.step == 1

        copy_of_section = section.copy()
        assert copy_of_section.step == 1

    def test_inject_messages_into_section(self):

        section, brief, form_data = self.setup_for_boolean_list_tests()

        section = ContentSection.create(section)
        section.inject_brief_questions_into_boolean_list_question(brief['briefs'])
        assert section.get_question('q0').get('boolean_list_questions') == brief['briefs']['q0']

    def test_inject_messages_into_section_optional_question_missing(self):

        section, brief, form_data = self.setup_for_boolean_list_tests()
        # add an optional boolean list question
        section['questions'].append({
            "id": "q1",
            "question": "Optional boolean list question",
            "type": "boolean_list",
            "optional": True
        })

        section = ContentSection.create(section)
        section.inject_brief_questions_into_boolean_list_question(brief['briefs'])
        assert section.get_question('q0').get('boolean_list_questions') == brief['briefs']['q0']

    def test_inject_messages_into_section_non_optional_question_missing(self):

        section, brief, form_data = self.setup_for_boolean_list_tests()
        # add an optional boolean list question
        brief['briefs'].pop("q0")

        section = ContentSection.create(section)
        with pytest.raises(ContentNotFoundError):
            section.inject_brief_questions_into_boolean_list_question(brief['briefs'])

    @pytest.mark.parametrize("summary_inplace_allowed", (False, True,))
    def test_inject_messages_into_section_and_section_summary(self, summary_inplace_allowed):

        section, brief, form_data = self.setup_for_boolean_list_tests()
        section['questions'].append({
            "id": "q1",
            "question": "Text question",
            "type": "text"
        })
        form_data['q1'] = 'Some text stuff'

        section = ContentSection.create(section)
        section.inject_brief_questions_into_boolean_list_question(brief['briefs'])
        response_data = section.get_data(form_data)
        section_summary = section.summary(response_data, inplace_allowed=summary_inplace_allowed)
        assert section_summary.get_question('q0').value == [True, True, True, True]
        assert section_summary.get_question('q0').get('boolean_list_questions') == brief['briefs']['q0']

        assert section_summary.get_question('q1').value == 'Some text stuff'
        assert section_summary.get_question('q1').get('boolean_list_questions') is None


class TestReadYaml(object):
    @mock.patch('dmcontent.content_loader.open', return_value=io.StringIO(u'foo: bar'))
    def test_loading_existant_file(self, mocked_open):
        assert read_yaml('anything.yml') == {'foo': 'bar'}

    @mock.patch('dmcontent.content_loader.open', side_effect=IOError)
    def test_file_not_found(self, mocked_open):
        with pytest.raises(IOError):
            assert read_yaml('something.yml')


@mock.patch('dmcontent.content_loader.read_yaml')
class TestContentLoader(object):
    yaml_file_count = 4

    def set_read_yaml_mock_response(self, read_yaml_mock):
        read_yaml_mock.side_effect = [
            self.manifest1(),
            self.question1(),
            self.question2(),
            self.question3()
        ]

    def manifest1(self):
        return [
            {"name": "section1", "questions": ["question1", "question2"]},
            {"name": "section2", "slug": "section-2", "prefill": True, "questions": ["question3"]}
        ]

    def question1(self):
        return {"name": "question1", "depends": [{"on": "lot", "being": "SaaS"}]}

    def question2(self):
        return {"id": "q2", "name": "question2", "depends": [{"on": "lot", "being": "SaaS"}]}

    def question3(self):
        return {"name": "question3", "depends": [{"on": "lot", "being": "IaaS"}]}

    def test_manifest_loading(self, read_yaml_mock):
        self.set_read_yaml_mock_response(read_yaml_mock)

        yaml_loader = ContentLoader('content/')

        sections = yaml_loader.load_manifest('framework-slug', 'question-set', 'my-manifest')

        assert sections == [
            {'name': TemplateField("section1"),
                'questions': [
                    {'depends': [{'being': 'SaaS', 'on': 'lot'}],
                     'name': TemplateField('question1'), 'slug': 'question1', 'id': 'question1'},
                    {'depends': [{'being': 'SaaS', 'on': 'lot'}],
                     'name': TemplateField('question2'), 'slug': 'q2', 'id': 'q2'}],
                'slug': 'section1'},
            {'name': TemplateField('section2'),
             'prefill': True,
             'questions': [
                 {'depends': [{'being': 'IaaS', 'on': 'lot'}],
                  'name': TemplateField('question3'), 'slug': 'question3', 'id': 'question3'}],
             'slug': 'section-2'}
        ]
        read_yaml_mock.assert_has_calls([
            mock.call('content/frameworks/framework-slug/manifests/my-manifest.yml'),
            mock.call('content/frameworks/framework-slug/questions/question-set/question1.yml'),
            mock.call('content/frameworks/framework-slug/questions/question-set/question2.yml'),
        ])

    def test_manifest_loading_cache(self, read_yaml_mock):
        self.set_read_yaml_mock_response(read_yaml_mock)

        yaml_loader = ContentLoader('content/')

        yaml_loader.load_manifest('framework-slug', 'question-set', 'my-manifest')
        yaml_loader.load_manifest('framework-slug', 'question-set', 'my-manifest')

        assert read_yaml_mock.call_count == self.yaml_file_count

    def test_manifest_loading_fails_if_manifest_cannot_be_read(self, read_yaml_mock):
        read_yaml_mock.side_effect = IOError

        yaml_loader = ContentLoader('content/')

        with pytest.raises(ContentNotFoundError):
            yaml_loader.load_manifest('framework-slug', 'question-set', 'my-manifest')

    def test_manifest_loading_fails_if_question_cannot_be_read(self, read_yaml_mock):
        read_yaml_mock.side_effect = [
            self.manifest1(),
            IOError
        ]

        yaml_loader = ContentLoader('content')

        with pytest.raises(ContentNotFoundError):
            yaml_loader.load_manifest('framework-slug', 'question-set', 'my-manifest')

    def test_lazy_loading_is_lazy(self, read_yaml_mock):
        self.set_read_yaml_mock_response(read_yaml_mock)
        yaml_loader = ContentLoader('content/')

        yaml_loader.lazy_load_manifests('framework-slug', {'my-manifest': 'question-set'})

        assert read_yaml_mock.call_count == 0

    def test_lazy_loading_loads(self, read_yaml_mock):
        self.set_read_yaml_mock_response(read_yaml_mock)
        yaml_loader = ContentLoader('content/')

        yaml_loader.lazy_load_manifests('framework-slug', {'my-manifest': 'question-set'})
        yaml_loader.get_manifest('framework-slug', 'my-manifest')

        assert read_yaml_mock.call_count == self.yaml_file_count

    def test_lazy_then_non_lazy_loads(self, read_yaml_mock):
        self.set_read_yaml_mock_response(read_yaml_mock)
        yaml_loader = ContentLoader('content/')

        yaml_loader.lazy_load_manifests('framework-slug', {'one-manifest': 'question-set'})
        yaml_loader.load_manifest('framework-slug', 'question-set', 'two-manifest')

        assert read_yaml_mock.call_count == self.yaml_file_count

    def test_non_lazy_then_lazy_loads(self, read_yaml_mock):
        self.set_read_yaml_mock_response(read_yaml_mock)
        yaml_loader = ContentLoader('content/')

        yaml_loader.load_manifest('framework-slug', 'question-set', 'one-manifest')
        yaml_loader.lazy_load_manifests('framework-slug', {'two-manifest': 'question-set'})

        assert read_yaml_mock.call_count == self.yaml_file_count

    def test_get_question(self, read_yaml_mock):
        read_yaml_mock.return_value = self.question1()

        yaml_loader = ContentLoader('content/')

        assert yaml_loader.get_question('framework-slug', 'question-set', 'question1') == {
            'depends': [{'being': 'SaaS', 'on': 'lot'}],
            'name': TemplateField('question1'), 'slug': 'question1', 'id': 'question1'
        }
        read_yaml_mock.assert_called_with(
            'content/frameworks/framework-slug/questions/question-set/question1.yml')

    def test_section_templatable_fields(self, read_yaml_mock):
        self.set_read_yaml_mock_response(read_yaml_mock)

        yaml_loader = ContentLoader('content/')

        section = yaml_loader._process_section('framework-slug', 'question-set', {
            "name": "section1",
            "description": "This is the first section",
            "prefill": False,
            "editable": True,
            "questions": []
        })

        assert section == {
            "name": TemplateField("section1"),
            "slug": "section1",
            "description": TemplateField("This is the first section"),
            "prefill": False,
            "editable": True,
            "questions": []
        }

    def test_get_question_templatable_fields(self, read_yaml_mock):
        read_yaml_mock.return_value = {
            "name": "question1",
            "question": "Question one",
            "question_advice": "This is the first question",
            "hint": "100 character limit",
            "type": "radios",
            "options": [
                {
                    "value": "Option 1",
                    "description": "This is the first option"
                }, {
                    "value": "Option 2",
                    "description": "This is the second option"
                },
            ],
            "validations": [
                {
                    "name": "answer_required",
                    "message": "You have to answer the question"
                }
            ]

        }

        yaml_loader = ContentLoader('content/')

        assert yaml_loader.get_question('framework-slug', 'question-set', 'question1') == {
            "id": "question1",
            "name": TemplateField("question1"),
            "slug": "question1",
            "question": TemplateField("Question one"),
            "question_advice": TemplateField("This is the first question"),
            "hint": TemplateField("100 character limit"),
            "type": "radios",
            "options": [
                {"value": "Option 1", "description": TemplateField("This is the first option")},
                {"value": "Option 2", "description": TemplateField("This is the second option")}
            ],
            "validations": [
                {"name": "answer_required", "message": TemplateField("You have to answer the question")}
            ]
        }
        read_yaml_mock.assert_called_with(
            'content/frameworks/framework-slug/questions/question-set/question1.yml')

    def test_get_question_question_advice_is_always_markdown(self, read_yaml_mock):
        read_yaml_mock.return_value = {
            "name": "question1",
            "question": "Question one",
            "question_advice": "This is the first question",
        }

        yaml_loader = ContentLoader('content/')
        question = yaml_loader.get_question('framework-slug', 'question-set', 'question1')
        question_advice = question["question_advice"]

        assert question_advice.markdown is True
        assert question_advice.render() == '<p class="govuk-body">This is the first question</p>'

    def test_get_question_uses_id_if_available(self, read_yaml_mock):
        read_yaml_mock.return_value = self.question2()

        yaml_loader = ContentLoader("content/")

        assert yaml_loader.get_question('framework-slug', 'question-set', 'question2') == {
            'depends': [{'being': 'SaaS', 'on': 'lot'}],
            'name': TemplateField('question2'), 'id': 'q2', 'slug': 'q2'
        }
        read_yaml_mock.assert_called_with(
            'content/frameworks/framework-slug/questions/question-set/question2.yml')

    def test_get_question_loads_nested_questions(self, read_yaml_mock):
        read_yaml_mock.side_effect = [
            {"name": "question1", "type": "multiquestion", "questions": ["question10", "question20"]},
            {"name": "question10", "type": "text"},
            {"name": "question20", "type": "checkboxes"},
        ]

        yaml_loader = ContentLoader('content/')

        assert yaml_loader.get_question('framework-slug', 'question-set', 'question1') == {
            "id": "question1",
            "slug": "question1",
            "name": TemplateField("question1"),
            "type": "multiquestion",
            "questions": [
                {"id": "question10", "name": TemplateField("question10"), "slug": "question10", "type": "text"},
                {"id": "question20", "name": TemplateField("question20"), "slug": "question20",
                 "type": "checkboxes"}
            ]
        }

        read_yaml_mock.assert_has_calls([
            mock.call('content/frameworks/framework-slug/questions/question-set/question1.yml'),
            mock.call('content/frameworks/framework-slug/questions/question-set/question10.yml'),
            mock.call('content/frameworks/framework-slug/questions/question-set/question20.yml'),
        ])

    def test_get_question_fails_if_question_cannot_be_read(self, read_yaml_mock):
        read_yaml_mock.side_effect = IOError

        yaml_loader = ContentLoader('content/')

        with pytest.raises(ContentNotFoundError):
            yaml_loader.get_question('framework-slug', 'question-set', 'question111')

    def test_get_same_question_id_from_same_question_set_only_loads_once(self, read_yaml_mock):
        read_yaml_mock.side_effect = [
            self.question1(),
        ]

        yaml_loader = ContentLoader('content/')
        yaml_loader.get_question('framework-slug', 'question-set-1', 'question1')
        yaml_loader.get_question('framework-slug', 'question-set-1', 'question1')

        read_yaml_mock.assert_has_calls([
            mock.call('content/frameworks/framework-slug/questions/question-set-1/question1.yml'),
        ])

    def test_get_same_question_id_from_different_question_sets(self, read_yaml_mock):
        read_yaml_mock.side_effect = [
            self.question1(),
            self.question1(),
        ]

        yaml_loader = ContentLoader('content/')
        yaml_loader.get_question('framework-slug', 'question-set-1', 'question1')
        yaml_loader.get_question('framework-slug', 'question-set-2', 'question1')

        read_yaml_mock.assert_has_calls([
            mock.call('content/frameworks/framework-slug/questions/question-set-1/question1.yml'),
            mock.call('content/frameworks/framework-slug/questions/question-set-2/question1.yml'),
        ])

    def test_get_question_returns_a_copy(self, read_yaml_mock):
        read_yaml_mock.return_value = self.question1()

        yaml_loader = ContentLoader('content/')

        q1 = yaml_loader.get_question('framework-slug', 'question-set', 'question1')
        q1["id"] = "modified"
        q1["depends"] = []

        assert yaml_loader.get_question('framework-slug', 'question-set', 'question1') != q1

    def test_get_message(self, mock_read_yaml):
        mock_read_yaml.return_value = {
            'field_one': 'value_one',
            'field_two': 'value_two',
        }
        messages = ContentLoader('content/')
        messages.load_messages('g-cloud-7', ['index'])

        assert messages.get_message('g-cloud-7', 'index') == ContentMessage({
            'field_one': TemplateField('value_one'),
            'field_two': TemplateField('value_two'),
        })

        assert messages.get_message('g-cloud-7', 'index').field_one == 'value_one'

    def test_get_message_with_key(self, mock_read_yaml):
        mock_read_yaml.return_value = {
            'field_one': 'value_one',
            'field_two': 'value_two',
        }
        messages = ContentLoader('content/')
        messages.load_messages('g-cloud-7', ['index'])

        assert messages.get_message('g-cloud-7', 'index', 'field_one') == 'value_one'

    def test_load_message_wraps_nested_fields_with_template_field(self, mock_read_yaml):
        mock_read_yaml.return_value = {
            'coming': {
                'heading': 'G-Cloud 7 is coming',
                'messages': ['Get ready', 'Other message'],
                'status': {
                    'open': 'open message',
                    'closed': u'closed message'
                }
            }
        }
        messages = ContentLoader('content/')
        messages.load_messages('g-cloud-7', ['index'])

        assert messages.get_message('g-cloud-7', 'index') == ContentMessage({
            'coming': {
                'heading': TemplateField('G-Cloud 7 is coming'),
                'messages': [TemplateField('Get ready'), TemplateField('Other message')],
                'status': {
                    'open': TemplateField('open message'),
                    'closed': TemplateField('closed message')
                }
            }
        })

        assert messages.get_message('g-cloud-7', 'index').coming.messages[0] == 'Get ready'

    def test_load_message_argument_types(self, mock_read_yaml):
        mock_read_yaml.return_value = {}
        messages = ContentLoader('content/')

        with pytest.raises(TypeError) as err:
            messages.load_messages('g-cloud-7', 'index')

        assert str(err.value) == 'Content blocks must be a list'

    def test_get_message_must_preload(self, mock_read_yaml):
        mock_read_yaml.return_value = {}
        messages = ContentLoader('content/')

        with pytest.raises(ContentNotFoundError):
            messages.get_message('g-cloud-8', 'dashboard')
            mock_read_yaml.assert_not_called()

    def test_load_message_raises(self, mock_read_yaml):
        mock_read_yaml.side_effect = IOError
        messages = ContentLoader('content/')

        with pytest.raises(ContentNotFoundError):
            messages.load_messages('not-a-framework', ['index'])

    def test_get_metadata(self, mock_read_yaml):
        mock_read_yaml.return_value = {
            'field_one': 'value_one',
            'field_two': 'value_two',
        }
        metadata = ContentLoader('content/')
        metadata.load_metadata('g-cloud-7', ['index'])

        assert metadata.get_metadata('g-cloud-7', 'index') == ContentMetadata({
            'field_one': 'value_one',
            'field_two': 'value_two',
        })

        assert metadata.get_metadata('g-cloud-7', 'index').field_one == 'value_one'

    def test_get_metadata_with_key(self, mock_read_yaml):
        mock_read_yaml.return_value = {
            'field_one': 'value_one',
            'field_two': 'value_two',
        }
        metadata = ContentLoader('content/')
        metadata.load_metadata('g-cloud-7', ['index'])

        assert metadata.get_metadata('g-cloud-7', 'index', 'field_one') == 'value_one'

    def test_load_metadata_does_not_mutate_values(self, mock_read_yaml):
        """When values are loaded into a ContentMessage, they are all wrapped as TemplateFieds. We want to make sure
        that nothing wraps the values for ContentMetadata as it is only static content."""
        mock_read_yaml.return_value = {
            'source_framework': 'g-cloud-6',
            'questions_to_copy': ['question-1', 'question-2']
        }
        metadata = ContentLoader('content/')
        metadata.load_metadata('g-cloud-7', ['copy_services'])

        assert metadata.get_metadata('g-cloud-7', 'copy_services') == ContentMetadata({
            'source_framework': 'g-cloud-6',
            'questions_to_copy': ['question-1', 'question-2']
        })

        assert metadata.get_metadata('g-cloud-7', 'copy_services').source_framework == 'g-cloud-6'

    def test_load_metadata_argument_types(self, mock_read_yaml):
        mock_read_yaml.return_value = {}
        metadata = ContentLoader('content/')

        with pytest.raises(TypeError) as err:
            metadata.load_metadata('g-cloud-7', 'index')

        assert str(err.value) == 'Content blocks must be a list'

    def test_get_metadata_must_preload(self, mock_read_yaml):
        mock_read_yaml.return_value = {}
        metadata = ContentLoader('content/')

        with pytest.raises(ContentNotFoundError):
            metadata.get_metadata('g-cloud-8', 'copy_services')
            mock_read_yaml.assert_not_called()

    def test_load_metadata_raises(self, mock_read_yaml):
        mock_read_yaml.side_effect = IOError
        metadata = ContentLoader('content/')

        with pytest.raises(ContentNotFoundError):
            metadata.load_metadata('not-a-framework', ['index'])

    def test_get_manifest(self, read_yaml_mock):
        self.set_read_yaml_mock_response(read_yaml_mock)

        yaml_loader = ContentLoader('content/')
        yaml_loader.load_manifest('framework-slug', 'question-set', 'manifest')

        builder = yaml_loader.get_manifest('framework-slug', 'manifest')
        assert isinstance(builder, ContentManifest)

        assert [
            section.id for section in builder.sections
        ] == ['section1', 'section-2']

    def test_multple_builders(self, read_yaml_mock):
        self.set_read_yaml_mock_response(read_yaml_mock)

        yaml_loader = ContentLoader('content/')
        yaml_loader.load_manifest('framework-slug', 'question-set', 'manifest')

        builder1 = yaml_loader.get_manifest('framework-slug', 'manifest')
        builder2 = yaml_loader.get_manifest('framework-slug', 'manifest')

        assert builder1 != builder2

    def test_get_manifest_fails_if_manifest_has_not_been_loaded(self, read_yaml_mock):
        with pytest.raises(ContentNotFoundError):
            yaml_loader = ContentLoader('content/')
            yaml_loader.get_manifest('framework-slug', 'manifest')


@pytest.mark.parametrize("title,slug", [
    ("The Title", "the-title"),
    ("This\nAnd\tThat ", "this-and-that"),
    ("This&That?", "this-that"),
    (u"This\u00a0That\u202f", "this-that"),
])
def test_make_slug(title, slug):
    assert _make_slug(title) == slug
