from __future__ import annotations

from django.test import SimpleTestCase
from spacy.language import Language as SpacyLanguage
from spacy.util import is_package

from book.nlp.tokenize import (
    get_tokenizer,
    tokenize_texts_to_half_candidates,
    tokenize_to_half_candidates,
)

JAPANESE_TEXT = """
は偷夬 であ つ た。 私 は 実に 先生 を この 雑沓の 間 に 見付け出 したので
かけ ぢ やや ある。 その 時 海岸に は掛 茶屋が 二 軒あった。 私 はふと した
機会から その 一 軒の 方に 行き 慣れて いた。 長 谷 辺 に 大きな 別荘 を 構えて
いる 人と 違って、 各自に 専有の き が え ば こしら 着換 場を栴 えてい ない
ここ いらの 避暑客に は、 ぜひ ともこう した 共同 着換 所と い つた 風な
ものが 必要な の であった。 彼ら
""".strip()

ENGLISH_TEXT = """
The impression I had was that we were leaving the West and entering the East;
the most western of splendid bridges over the Danube, which is here of noble
width and depth, took us among the traditions of Turkish rule.

We left in pretty good time, and came after nightfall to Klausenburgh. Here I
stopped for the night at the Hotel Royale. I had for dinner, or rather supper,
a chicken done up some way with red pepper, which was very good but thirsty.
(Mem. get recipe for Mina.) I asked the waiter, and he said it was called
"paprika hendl," and that, as it was a national dish, I should be able to get
it anywhere along the Carpathians.

I found my smattering of German very useful here, indeed, I don't know how I
should be able to get on without it.

Having had some time at my disposal when in London, I had visited the British
Museum, and made search among the books and maps in the library regarding
Transylvania; it had struck me that some foreknowledge of the country could
hardly fail to have some importance in dealing with a nobleman of that country.

I find that the district he named is in the extreme east of the country, just
on the borders of three states, Transylvania, Moldavia, and Bukovina, in the
midst of the Carpathian mountains; one of the wildest and least known portions
of Europe.

I was not able to light on any map or work giving the exact locality of the
Castle Dracula, as there are no maps of this country as yet to compare with
our own Ordance Survey Maps; but I found that Bistritz, the post town named by
Count Dracula, is a fairly well-known place. I shall enter here some of my
notes, as they may refresh my memory when I talk over my travels with Mina.

In the population of Transylvania there are four distinct nationalities:
Saxons in the South, and mixed with them the Wallachs, who are the descendants
of the Dacians; Magyars in the West, and Szekelys in the East and North. I am
going among the latter, who claim to be descended from Attila and the Huns.
This may be so, for when the Magyars conquered the country in the eleventh
century they found the Huns settled in it.

I read that every known superstition in the world is gathered into the
horseshoe of the Carpathians, as if it were the centre of some sort of
imaginative whirlpool; if so my stay may be very interesting. (Mem., I must ask
the Count all about them.)

I did not sleep well, though my bed was comfortable enough, for I had all sorts
of queer dreams. There was a dog howling all night under my window, which may
have had something to do with it; or it may have been the paprika, for I had to
drink up all the water in my carafe, and was still thirsty. Towards morning I
slept and was wakened by the continuous knocking at my door, so I guess I must
have been sleeping soundly then.

I had for breakfast more paprika, and a sort of porridge of maize flour which
they said was "mamaliga", and egg-plant stuffed with forcemeat, a very
excellent dish, which they call "impletata". (Mem.,get recipe for this also.)

I had to hurry breakfast, for the train started a little before eight, or
rather it ought to have done so, for after rushing to the station at 7:30 I had
to sit in the carriage for more than an hour before we began to move.

It seems to me that the further east you go the more unpunctual are the trains.
What ought they to be in China?

All day long we seemed to dawdle through a country which was full of beauty of
every kind. Sometimes we saw little towns or castles on the top of steep hills
such as we see in old missals; sometimes we ran by rivers and streams which
seemed from the wide stony margin on each side of them to be subject ot great
floods. It takes a lot of water, and running strong, to sweep the outside edge
of a river clear.

At every station there were groups of people, sometimes crowds, and in all
sorts of attire. Some of them were just like the peasants at home or those I
saw coming through France and Germany, with short jackets, and round hats, and
home-made trousers; but others were very picturesque.

The women looked pretty, except when you got near them, but they were very
clumsy about the waist. They had all full white sleeves of some kind or other,
and most of them had big belts with a lot of strips of something fluttering
from them like the dresses in a ballet, but of course there were petticoats
under them.

The strangest figures we saw were the Slovaks, who were more barbarian than the
rest, with their big cow-boy hats, great baggy dirty-white trousers, white
linen shirts, and enormous heavy leather belts, nearly a foot wide, all studded
over with brass nails. They wore high boots, with their trousers tucked into
them, and had long black hair and heavy black moustaches. They are very
picturesque, but do not look prepossessing. On the stage they would be set down
at once as some old Oriental band of brigands. They are, however, I am told,
very harmless and rather wanting in natural self-assertion.
""".strip()

# Add compact variants to guarantee a multi-surface base-form case.
ENGLISH_VARIANT_SUFFIX = " He is, was, and be."
JAPANESE_VARIANT_SUFFIX = " 食べる 食べた 食べます。"


class TokenizeIntegrationTests(SimpleTestCase):
    def setUp(self):
        get_tokenizer.cache_clear()

    def _skip_if_model_missing(self, model_name: str) -> None:
        if not is_package(model_name):
            self.skipTest(f"spaCy model '{model_name}' is not installed.")

    def _assert_desc_frequency_order(self, candidates: list[dict]) -> None:
        counts = [item["total_count"] for item in candidates]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_get_tokenizer_loads_english_pipeline(self):
        self._skip_if_model_missing("en_core_web_sm")

        tokenizer = get_tokenizer("en")

        self.assertIsInstance(tokenizer, SpacyLanguage)
        self.assertEqual(tokenizer.lang, "en")

    def test_get_tokenizer_loads_japanese_pipeline(self):
        self._skip_if_model_missing("ja_core_news_sm")

        tokenizer = get_tokenizer("ja")

        self.assertIsInstance(tokenizer, SpacyLanguage)
        self.assertEqual(tokenizer.lang, "ja")

    def test_english_tokenizer_returns_half_candidate_list_sorted(self):
        self._skip_if_model_missing("en_core_web_sm")

        candidates = tokenize_texts_to_half_candidates(
            [ENGLISH_TEXT + ENGLISH_VARIANT_SUFFIX],
            language="en",
        )

        self.assertIsInstance(candidates, list)
        self.assertGreater(len(candidates), 0)
        self.assertIn("base", candidates[0])
        self.assertIn("total_count", candidates[0])
        self.assertIn("surface_forms", candidates[0])
        self.assertIn("pos_counts", candidates[0])
        self.assertIsInstance(candidates[0]["surface_forms"], set)
        self._assert_desc_frequency_order(candidates)

    def test_japanese_tokenizer_returns_half_candidate_list_sorted(self):
        self._skip_if_model_missing("ja_core_news_sm")

        candidates = tokenize_to_half_candidates(
            JAPANESE_TEXT + JAPANESE_VARIANT_SUFFIX,
            language="ja",
        )

        self.assertIsInstance(candidates, list)
        self.assertGreater(len(candidates), 0)
        self.assertIn("base", candidates[0])
        self.assertIn("total_count", candidates[0])
        self.assertIn("surface_forms", candidates[0])
        self.assertIn("pos_counts", candidates[0])
        self.assertIsInstance(candidates[0]["surface_forms"], set)
        self._assert_desc_frequency_order(candidates)

    def test_english_has_multi_surface_base_when_applicable(self):
        self._skip_if_model_missing("en_core_web_sm")

        candidates = tokenize_texts_to_half_candidates(
            [ENGLISH_TEXT + ENGLISH_VARIANT_SUFFIX],
            language="en",
        )

        has_multi_surface = any(
            len(item["surface_forms"]) > 1 and item["total_count"] > 1
            for item in candidates
        )
        self.assertTrue(has_multi_surface)

    def test_japanese_has_multi_surface_base_when_applicable(self):
        self._skip_if_model_missing("ja_core_news_sm")

        candidates = tokenize_to_half_candidates(
            JAPANESE_TEXT + JAPANESE_VARIANT_SUFFIX,
            language="ja",
        )

        has_multi_surface = any(
            len(item["surface_forms"]) > 1 and item["total_count"] > 1
            for item in candidates
        )
        self.assertTrue(has_multi_surface)
