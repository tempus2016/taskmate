# Bonuses

Bonuses are a point-awarding system that complements the Penalties system. While Penalties deduct points for negative behaviors, Bonuses award points for positive achievements and special occasions.

## Overview

The Bonuses feature allows you to:
- **Create custom bonuses** that award points to children
- **Manage bonuses** through the Bonuses card in your dashboard
- **Apply bonuses** instantly via the UI or services
- **Assign bonuses** to specific children or all children
- **Categorize bonuses** with icons and descriptions

## How Bonuses Work

1. **Create a Bonus** - Define a bonus with a name, point value, optional description, and icon
2. **Assign It** - Choose which children the bonus applies to (or leave empty for all)
3. **Apply the Bonus** - Award the points to a child through the Bonuses card or via service call
4. **Points Awarded** - The child receives the bonus points immediately in their account

### Bonuses vs Penalties

| Aspect | Bonuses | Penalties |
|--------|---------|-----------|
| **Purpose** | Reward positive behaviors | Discourage negative behaviors |
| **Point Effect** | Awards points (+) | Deducts points (-) |
| **Common Use Cases** | Perfect week, good report card, extra chores | Rule breaking, incomplete chores, screen time violations |
| **Trigger** | Parent recognition, special events | Behavioral issues, incomplete tasks |

## The Bonuses Card

The Bonuses Card provides a green-themed interface for managing all your bonuses. Key features:

- **List of Bonuses** - View all defined bonuses with their point values
- **Add New Bonus** - Create a new bonus definition directly from the card
- **Apply Bonus** - Select a child and click the bonus to award points
- **Edit/Delete** - Manage existing bonuses
- **Visual Indicators** - Color-coded icons help distinguish different bonus types

### Lovelace Configuration

Add the Bonuses Card to your dashboard:

```yaml
type: custom:taskmate-bonuses-card
entity: sensor.taskmate_overview
title: Bonuses
```

## Creating and Managing Bonuses

### Create a Bonus

1. Open the Bonuses Card on your dashboard
2. Click "Add Bonus" or the **+** button
3. Fill in the bonus details:
   - **Name** - The bonus title (e.g., "Perfect Week")
   - **Points** - Points awarded when applied (1-10000)
   - **Description** (optional) - Details about when to use this bonus
   - **Icon** (optional) - MDI icon for visual identification
   - **Assigned To** (optional) - Specific children (leave empty for all)
4. Click Save

### Update a Bonus

1. In the Bonuses Card, click the **edit** icon on the bonus
2. Modify the desired fields
3. Click Save

### Remove a Bonus

1. In the Bonuses Card, click the **delete** icon on the bonus
2. Confirm the deletion

### Apply a Bonus

1. In the Bonuses Card, select a child from the dropdown
2. Click the bonus you want to apply
3. The points are instantly awarded to that child

## Services

The Bonuses system provides four services for advanced automation:

### taskmate.add_bonus
Create a new bonus definition.

### taskmate.update_bonus
Update an existing bonus definition.

### taskmate.remove_bonus
Remove a bonus definition.

### taskmate.apply_bonus
Award bonus points to a child (calls the internal `add_points` service).

See the [Services](Services) page for detailed parameter documentation and YAML examples.

## Common Use Cases

### Perfect Week Bonus
Award extra points when a child completes all assigned chores in a week.

**Bonus Details:**
- Name: "Perfect Week"
- Points: 25
- Description: "Completed all chores for the week"
- Icon: `mdi:star`

### Report Card Bonus
Reward good grades or school achievements.

**Bonus Details:**
- Name: "Great Grades"
- Points: 50
- Description: "Honor roll or excellent report card"
- Icon: `mdi:school`

### Special Event Bonus
Celebrate birthdays, holidays, or milestones.

**Bonus Details:**
- Name: "Birthday Bonus"
- Points: 100
- Description: "Happy Birthday!"
- Icon: `mdi:birthday-cake`

### Chore Motivation Bonus
Quick bonuses for exceeding expectations.

**Bonus Details:**
- Name: "Extra Effort"
- Points: 10
- Description: "Completed a chore ahead of schedule"
- Icon: `mdi:lightning-bolt`

## Tips & Best Practices

**Start Simple** - Begin with a few bonuses (Perfect Week, Good Grades, Birthday) and expand based on your family's needs.

**Balance Your Economy** - Keep bonus point values reasonable compared to chore rewards to maintain motivation balance. Example: If chores award 5-20 points, bonuses might award 10-50 points.

**Use Icons Consistently** - Choose recognizable MDI icons that make bonuses instantly identifiable on the card.

**Assign Strategically** - Use assignment to create age-appropriate bonuses. Younger children might have simpler bonus criteria.

**Celebrate Often** - Bonuses are more effective when applied promptly and for genuine achievements. Don't overuse them.

**Combine with Automations** - Use the `apply_bonus` service in automations to award bonuses based on Home Assistant sensor values (e.g., door lock, presence, weather).

## Troubleshooting

**Bonus Not Appearing on Card**
- Verify the bonus was saved (check the card's bonus list)
- Refresh your dashboard (F5 or hard refresh)
- Check that the `sensor.taskmate_overview` entity is available

**Can't Apply Bonus**
- Ensure a child is selected from the dropdown
- Verify the bonus is assigned to that child (or assigned to all if "Assigned To" is empty)
- Check Home Assistant logs for errors

**Points Not Awarded**
- Confirm the child's point balance increased after applying the bonus
- Verify the `apply_bonus` service is properly configured (if using automations)
- Check that the bonus points value is correctly set

**Service Call Fails**
- Verify the `bonus_id` and `child_id` are correct (use Developer Tools to find IDs)
- Ensure the bonus and child still exist
- Check Home Assistant logs for detailed error messages
