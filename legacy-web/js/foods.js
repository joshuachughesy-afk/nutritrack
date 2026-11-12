// Built-in reference foods. Values per 100 g, approximated from USDA FoodData Central (SR Legacy / Foundation).
// Columns: [kcal, protein, carbs, fat, fiber, sugar]
//          [sodium, potassium, calcium, iron, magnesium, zinc, vitA µg RAE, vitC, vitD µg, vitE, vitK µg, b12 µg, folate µg DFE]

const MICRO_ORDER = ['sodium', 'potassium', 'calcium', 'iron', 'magnesium', 'zinc', 'vitA', 'vitC', 'vitD', 'vitE', 'vitK', 'b12', 'folate'];

function f(id, name, category, servings, [kcal, protein, carbs, fat, fiber, sugar], micros) {
  const per100 = { kcal, protein, carbs, fat, fiber, sugar };
  MICRO_ORDER.forEach((k, i) => (per100[k] = micros[i] || 0));
  return { id, name, category, servings, per100, source: 'USDA' };
}

export const FOODS = [
  // Protein
  f('chicken-breast', 'Chicken breast, cooked', 'Protein', [{ label: '1 breast (172 g)', g: 172 }, { label: '1 portion (85 g)', g: 85 }], [165, 31, 0, 3.6, 0, 0], [74, 256, 15, 1.0, 29, 1.0, 6, 0, 0.1, 0.3, 0.3, 0.3, 4]),
  f('egg', 'Egg, whole', 'Protein', [{ label: '1 large egg', g: 50 }], [143, 12.6, 0.7, 9.5, 0, 0.4], [142, 138, 56, 1.75, 12, 1.3, 160, 0, 2.0, 1.05, 0.3, 0.89, 47]),
  f('egg-white', 'Egg white', 'Protein', [{ label: '1 large white', g: 33 }], [52, 10.9, 0.7, 0.2, 0, 0.7], [166, 163, 7, 0.08, 11, 0.03, 0, 0, 0, 0, 0, 0.09, 4]),
  f('salmon', 'Salmon, Atlantic, cooked', 'Protein', [{ label: '1 fillet (154 g)', g: 154 }, { label: '1 portion (85 g)', g: 85 }], [206, 22.1, 0, 12.4, 0, 0], [61, 384, 15, 0.34, 30, 0.43, 69, 3.7, 13.1, 1.1, 0.5, 2.8, 34]),
  f('tuna-canned', 'Tuna, canned in water', 'Protein', [{ label: '1 can drained (142 g)', g: 142 }], [116, 25.5, 0, 0.8, 0, 0], [247, 237, 11, 1.5, 27, 0.7, 17, 0, 1.7, 0.33, 0, 2.99, 4]),
  f('beef-90', 'Ground beef 90% lean, cooked', 'Protein', [{ label: '1 patty (113 g)', g: 113 }, { label: '1 portion (85 g)', g: 85 }], [217, 26.1, 0, 11.7, 0, 0], [76, 370, 12, 2.7, 22, 6.3, 0, 0, 0.1, 0.4, 1.2, 2.5, 9]),
  f('pork-loin', 'Pork loin, cooked', 'Protein', [{ label: '1 portion (85 g)', g: 85 }], [196, 27.3, 0, 8.9, 0, 0], [60, 390, 20, 0.9, 28, 2.6, 2, 0.6, 0.6, 0.2, 0, 0.7, 2]),
  f('shrimp', 'Shrimp, cooked', 'Protein', [{ label: '1 portion (85 g)', g: 85 }], [99, 24, 0.2, 0.3, 0, 0], [111, 259, 70, 0.5, 39, 1.6, 0, 0, 0, 1.4, 0, 1.1, 3]),
  f('tofu', 'Tofu, firm (calcium-set)', 'Protein', [{ label: '½ cup (126 g)', g: 126 }], [144, 17.3, 2.8, 8.7, 2.3, 0.6], [14, 237, 683, 2.7, 58, 1.6, 0, 0.2, 0, 0, 2.4, 0, 29]),
  f('whey', 'Whey protein powder (generic, check label)', 'Protein', [{ label: '1 scoop (30 g)', g: 30 }], [400, 80, 8, 6, 0, 4], [300, 500, 450, 1, 100, 2, 0, 0, 0, 0, 0, 1, 0]),

  // Dairy
  f('greek-yogurt', 'Greek yogurt, plain nonfat', 'Dairy', [{ label: '1 container (170 g)', g: 170 }, { label: '1 cup (245 g)', g: 245 }], [59, 10.2, 3.6, 0.4, 0, 3.2], [36, 141, 110, 0.07, 11, 0.52, 1, 0, 0, 0.01, 0, 0.75, 7]),
  f('milk-2', 'Milk, 2%', 'Dairy', [{ label: '1 cup (244 g)', g: 244 }], [50, 3.3, 4.8, 2.0, 0, 5.1], [47, 140, 120, 0.03, 11, 0.4, 55, 0, 1.1, 0.03, 0.2, 0.5, 5]),
  f('cheddar', 'Cheddar cheese', 'Dairy', [{ label: '1 slice (28 g)', g: 28 }], [403, 22.9, 3.1, 33.1, 0, 0.5], [653, 76, 710, 0.14, 27, 3.6, 265, 0, 0.6, 0.7, 2.4, 1.1, 27]),
  f('cottage-cheese', 'Cottage cheese, 2%', 'Dairy', [{ label: '½ cup (113 g)', g: 113 }], [81, 10.5, 4.8, 2.3, 0, 4.0], [308, 125, 111, 0.13, 9, 0.5, 22, 0, 0, 0.02, 0, 0.47, 13]),

  // Grains & starches
  f('oats', 'Oats, rolled (dry)', 'Grains', [{ label: '½ cup dry (40 g)', g: 40 }], [379, 13.2, 67.7, 6.5, 10.1, 1.0], [6, 362, 52, 4.3, 138, 3.6, 0, 0, 0, 0.4, 2.0, 0, 32]),
  f('rice-white', 'White rice, cooked', 'Grains', [{ label: '1 cup (158 g)', g: 158 }], [130, 2.7, 28.2, 0.3, 0.4, 0.05], [1, 35, 10, 1.2, 12, 0.5, 0, 0, 0, 0.04, 0, 0, 58]),
  f('rice-brown', 'Brown rice, cooked', 'Grains', [{ label: '1 cup (195 g)', g: 195 }], [123, 2.7, 25.6, 1.0, 1.6, 0.2], [4, 86, 3, 0.56, 39, 0.7, 0, 0, 0, 0.1, 0.2, 0, 9]),
  f('quinoa', 'Quinoa, cooked', 'Grains', [{ label: '1 cup (185 g)', g: 185 }], [120, 4.4, 21.3, 1.9, 2.8, 0.9], [7, 172, 17, 1.5, 64, 1.1, 0, 0, 0, 0.63, 0, 0, 42]),
  f('pasta', 'Pasta, cooked (enriched)', 'Grains', [{ label: '1 cup (140 g)', g: 140 }], [158, 5.8, 30.9, 0.9, 1.8, 0.6], [1, 44, 7, 1.3, 18, 0.5, 0, 0, 0, 0.06, 0, 0, 72]),
  f('bread-ww', 'Whole wheat bread', 'Grains', [{ label: '1 slice (32 g)', g: 32 }], [252, 12.4, 42.7, 3.5, 6.0, 4.4], [455, 254, 161, 2.5, 76, 1.8, 0, 0, 0, 0.3, 7.8, 0, 42]),
  f('potato', 'Potato, baked with skin', 'Grains', [{ label: '1 medium (173 g)', g: 173 }], [93, 2.5, 21.2, 0.1, 2.2, 1.2], [10, 535, 15, 1.1, 28, 0.4, 1, 9.6, 0, 0.04, 2.0, 0, 28]),
  f('sweet-potato', 'Sweet potato, baked', 'Grains', [{ label: '1 medium (114 g)', g: 114 }], [90, 2.0, 20.7, 0.2, 3.3, 6.5], [36, 475, 38, 0.69, 27, 0.32, 961, 19.6, 0, 0.71, 2.3, 0, 6]),

  // Legumes
  f('black-beans', 'Black beans, cooked', 'Legumes', [{ label: '½ cup (86 g)', g: 86 }], [132, 8.9, 23.7, 0.5, 8.7, 0.3], [1, 355, 27, 2.1, 70, 1.1, 0, 0, 0, 0.9, 3.3, 0, 149]),
  f('lentils', 'Lentils, cooked', 'Legumes', [{ label: '½ cup (99 g)', g: 99 }], [116, 9.0, 20.1, 0.4, 7.9, 1.8], [2, 369, 19, 3.3, 36, 1.3, 0, 1.5, 0, 0.1, 1.7, 0, 181]),

  // Vegetables
  f('broccoli', 'Broccoli, cooked', 'Vegetables', [{ label: '1 cup (156 g)', g: 156 }], [35, 2.4, 7.2, 0.4, 3.3, 1.4], [41, 293, 40, 0.67, 21, 0.45, 77, 64.9, 0, 1.45, 141, 0, 108]),
  f('spinach', 'Spinach, raw', 'Vegetables', [{ label: '1 cup (30 g)', g: 30 }], [23, 2.9, 3.6, 0.4, 2.2, 0.4], [79, 558, 99, 2.7, 79, 0.53, 469, 28.1, 0, 2.0, 483, 0, 194]),
  f('kale', 'Kale, raw', 'Vegetables', [{ label: '1 cup chopped (21 g)', g: 21 }], [35, 2.9, 4.4, 1.5, 4.1, 1.0], [53, 348, 254, 1.6, 33, 0.39, 241, 93.4, 0, 0.66, 390, 0, 62]),
  f('carrot', 'Carrot, raw', 'Vegetables', [{ label: '1 medium (61 g)', g: 61 }], [41, 0.9, 9.6, 0.2, 2.8, 4.7], [69, 320, 33, 0.3, 12, 0.24, 835, 5.9, 0, 0.66, 13.2, 0, 19]),
  f('tomato', 'Tomato, raw', 'Vegetables', [{ label: '1 medium (123 g)', g: 123 }], [18, 0.9, 3.9, 0.2, 1.2, 2.6], [5, 237, 10, 0.27, 11, 0.17, 42, 13.7, 0, 0.54, 7.9, 0, 15]),
  f('bell-pepper', 'Bell pepper, red, raw', 'Vegetables', [{ label: '1 medium (119 g)', g: 119 }], [31, 1.0, 6.0, 0.3, 2.1, 4.2], [4, 211, 7, 0.43, 12, 0.25, 157, 127.7, 0, 1.58, 4.9, 0, 46]),
  f('avocado', 'Avocado', 'Vegetables', [{ label: '½ avocado (68 g)', g: 68 }], [160, 2.0, 8.5, 14.7, 6.7, 0.7], [7, 485, 12, 0.55, 29, 0.64, 7, 10, 0, 2.07, 21, 0, 81]),

  // Fruit
  f('banana', 'Banana', 'Fruit', [{ label: '1 medium (118 g)', g: 118 }], [89, 1.1, 22.8, 0.3, 2.6, 12.2], [1, 358, 5, 0.26, 27, 0.15, 3, 8.7, 0, 0.1, 0.5, 0, 20]),
  f('apple', 'Apple', 'Fruit', [{ label: '1 medium (182 g)', g: 182 }], [52, 0.3, 13.8, 0.2, 2.4, 10.4], [1, 107, 6, 0.12, 5, 0.04, 3, 4.6, 0, 0.18, 2.2, 0, 3]),
  f('orange', 'Orange', 'Fruit', [{ label: '1 medium (131 g)', g: 131 }], [47, 0.9, 11.8, 0.1, 2.4, 9.4], [0, 181, 40, 0.1, 10, 0.07, 11, 53.2, 0, 0.18, 0, 0, 30]),
  f('blueberries', 'Blueberries', 'Fruit', [{ label: '1 cup (148 g)', g: 148 }], [57, 0.7, 14.5, 0.3, 2.4, 10.0], [1, 77, 6, 0.28, 6, 0.16, 3, 9.7, 0, 0.57, 19.3, 0, 6]),
  f('strawberries', 'Strawberries', 'Fruit', [{ label: '1 cup halves (152 g)', g: 152 }], [32, 0.7, 7.7, 0.3, 2.0, 4.9], [1, 153, 16, 0.41, 13, 0.14, 1, 58.8, 0, 0.29, 2.2, 0, 24]),
  f('oj', 'Orange juice', 'Fruit', [{ label: '1 cup (248 g)', g: 248 }], [45, 0.7, 10.4, 0.2, 0.2, 8.4], [1, 200, 11, 0.2, 11, 0.05, 10, 50, 0, 0.04, 0.1, 0, 30]),

  // Fats, nuts, seeds
  f('almonds', 'Almonds', 'Nuts & fats', [{ label: '1 handful (28 g, ~23 nuts)', g: 28 }], [579, 21.2, 21.6, 49.9, 12.5, 4.4], [1, 733, 269, 3.7, 270, 3.1, 0, 0, 0, 25.6, 0, 0, 44]),
  f('peanut-butter', 'Peanut butter', 'Nuts & fats', [{ label: '1 tbsp (16 g)', g: 16 }, { label: '2 tbsp (32 g)', g: 32 }], [588, 25.1, 20, 50.4, 6.0, 9.2], [429, 649, 49, 1.9, 154, 2.9, 0, 0, 0, 9.0, 0.3, 0, 87]),
  f('olive-oil', 'Olive oil', 'Nuts & fats', [{ label: '1 tbsp (13.5 g)', g: 13.5 }, { label: '1 tsp (4.5 g)', g: 4.5 }], [884, 0, 0, 100, 0, 0], [2, 1, 1, 0.56, 0, 0, 0, 0, 0, 14.4, 60.2, 0, 0]),
  f('chia', 'Chia seeds', 'Nuts & fats', [{ label: '1 tbsp (12 g)', g: 12 }], [486, 16.5, 42.1, 30.7, 34.4, 0], [16, 407, 631, 7.7, 335, 4.6, 0, 1.6, 0, 0.5, 0, 0, 49]),
  f('dark-chocolate', 'Dark chocolate 70–85%', 'Nuts & fats', [{ label: '1 square (10 g)', g: 10 }, { label: '3 squares (28 g)', g: 28 }], [598, 7.8, 45.9, 42.6, 10.9, 24], [20, 715, 73, 11.9, 228, 3.3, 2, 0, 0, 0.6, 7.3, 0.3, 0]),
];

export const FOOD_CATEGORIES = [...new Set(FOODS.map(x => x.category))];
