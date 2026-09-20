import type { SemanticResponse } from '../types';
import { humanize } from './format';

/** Opening questions built from the columns this dataset actually has, so the
 *  first thing a new user clicks returns a real answer rather than an error. */
export function starterQuestions(semantic: SemanticResponse | null): string[] {
  if (!semantic) return [];

  const columns = semantic.tables.flatMap((table) => Object.values(table.columns));
  const measure = columns.find((column) => column.role === 'measure');
  const dimensions = columns.filter((column) => column.role === 'dimension');
  const hasTime = columns.some((column) => column.role === 'time');

  const metric = measure ? humanize(measure.display_name || measure.name).toLowerCase() : 'revenue';
  const questions: string[] = [`What is total ${metric}?`];

  if (hasTime) {
    questions.push(`Show ${metric} by month`);
    questions.push(`Why did ${metric} change last month?`);
  }

  const firstDimension = dimensions[0];
  if (firstDimension) {
    const label = humanize(firstDimension.display_name || firstDimension.name).toLowerCase();
    questions.push(`${humanize(metric)} by ${label}`);
  }

  return questions.slice(0, 4);
}
