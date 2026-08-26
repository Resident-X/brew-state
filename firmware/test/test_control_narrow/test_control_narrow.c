/*
 * The control path's question about delivery-point contention, asked against a
 * structure that serves its two points from two heated masses.
 *
 * The suite beside this one runs the control logic against the structure that
 * describes the reference machine, which routes both its delivery points out of
 * one casting. Every contention answer there is "yes", and an implementation
 * that had compiled that answer in rather than asking the seam would pass every
 * one of them. This is the other structure: it declares the group and the spout
 * on separate masses, so the only way to answer "no" here is to have asked.
 *
 * It is deliberately narrow. Nothing here brings a loop up or steps one --
 * the structure behind this build describes no machine, draws no water at full
 * pump and keeps no state for the water on its way to a group, so a loop closed
 * around it would be asserting things about a machine that is not there. What
 * is asked here is the one question that is answerable without a machine:
 * whether two named delivery points are backed by the same heated mass, put to
 * the seam by the control path rather than answered from a table.
 */
#include <unity.h>

#include "control.h"
#include "delivery_profile.h"
#include "plant_model.h"

void setUp(void) {}
void tearDown(void) {}

/* A one-second course at a steady rate, arriving at a stated point. */
static delivery_profile_t course_arriving_at(plant_delivery_point_t served_at)
{
    const delivery_profile_point_t points[] = {{0u, 1.0f}, {1000u, 1.0f}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 1000u};
    delivery_profile_t course;

    TEST_ASSERT_TRUE(delivery_profile_init(&course, points, 2u, end, served_at));
    return course;
}

/// SOL-BREW-RECOVERS-AFTER-DRAW.C2: Which heated mass a delivery draws from is
/// asked of the plant seam rather than assumed.
///
/// A structure declaring its two points on separate masses answers that they do
/// not contend, and is owed no recovery account. This is the check that the
/// control path asks the question rather than describing one machine's
/// plumbing: the same call, against the structure that serves both points from
/// one casting, answers that they do contend, and an implementation returning
/// either answer unconditionally fails one of the two suites.
static void test_two_points_on_two_masses_do_not_contend(void)
{
    const delivery_profile_t at_the_spout =
        course_arriving_at(PLANT_DELIVERY_POINT_HOT_WATER_SPOUT);
    bool contends = true;

    TEST_ASSERT_TRUE(control_delivery_contends_with_the_group(&at_the_spout, &contends));
    TEST_ASSERT_FALSE_MESSAGE(contends,
                              "this structure serves its two points from two heated masses, and "
                              "the control path answered that a delivery at the spout contends "
                              "with the group");
}

/// SOL-BREW-RECOVERS-AFTER-DRAW.C2: Which heated mass a delivery draws from is
/// asked of the plant seam rather than assumed.
///
/// The group contends with itself whatever the structure is, because it is the
/// same mass by definition. Without this, an implementation that simply
/// answered "no" to everything would pass the case above while establishing
/// nothing.
static void test_the_group_contends_with_itself_on_any_structure(void)
{
    const delivery_profile_t at_the_group = course_arriving_at(PLANT_DELIVERY_POINT_GROUP);
    bool contends = false;

    TEST_ASSERT_TRUE(control_delivery_contends_with_the_group(&at_the_group, &contends));
    TEST_ASSERT_TRUE_MESSAGE(contends,
                             "the group was answered as not contending with itself, so the answer "
                             "is not composed from the mass behind each point");
}

/// SOL-BREW-RECOVERS-AFTER-DRAW.C2: Which heated mass a delivery draws from is
/// asked of the plant seam rather than assumed.
///
/// The answer is composed from what this structure declares rather than from
/// anything the control path holds. Reading the two masses back through the
/// seam and requiring them to differ is what makes the refusal above evidence
/// about this structure rather than about the call.
static void test_the_answer_follows_the_masses_this_structure_declares(void)
{
    plant_heated_mass_id_t group_mass = 0u;
    plant_heated_mass_id_t spout_mass = 0u;

    TEST_ASSERT_TRUE(plant_structure_delivery_point_mass(PLANT_DELIVERY_POINT_GROUP, &group_mass));
    TEST_ASSERT_TRUE(
        plant_structure_delivery_point_mass(PLANT_DELIVERY_POINT_HOT_WATER_SPOUT, &spout_mass));
    TEST_ASSERT_NOT_EQUAL_UINT8_MESSAGE(group_mass, spout_mass,
                                        "this structure no longer declares its two points on two "
                                        "masses, so the case above is not about a machine that "
                                        "does");
}

/// SOL-BREW-RECOVERS-AFTER-DRAW.C2: Which heated mass a delivery draws from is
/// asked of the plant seam rather than assumed.
///
/// A profile naming a point outside the machine's vocabulary is refused where
/// it is built, on the same structure-independent terms it is refused against
/// any other: the vocabulary is the machine's rather than a structure's, so a
/// build against a structure that serves fewer points still refuses the same
/// values at construction and refuses the unserved ones at the seam.
static void test_a_point_outside_the_vocabulary_is_refused_here_too(void)
{
    const delivery_profile_point_t points[] = {{0u, 1.0f}, {1000u, 1.0f}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 1000u};
    delivery_profile_t profile;

    TEST_ASSERT_FALSE(delivery_profile_init(&profile, points, 2u, end,
                                            (plant_delivery_point_t)PLANT_DELIVERY_POINT_COUNT));

    delivery_profile_t nowhere = course_arriving_at(PLANT_DELIVERY_POINT_GROUP);
    nowhere.served_at = (plant_delivery_point_t)PLANT_DELIVERY_POINT_COUNT;

    bool contends = false;
    TEST_ASSERT_FALSE_MESSAGE(control_delivery_contends_with_the_group(&nowhere, &contends),
                              "a point this structure does not serve was answered rather than "
                              "refused");
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_two_points_on_two_masses_do_not_contend);
    RUN_TEST(test_the_group_contends_with_itself_on_any_structure);
    RUN_TEST(test_the_answer_follows_the_masses_this_structure_declares);
    RUN_TEST(test_a_point_outside_the_vocabulary_is_refused_here_too);
    return UNITY_END();
}
