from dataclasses import dataclass
from fractions import Fraction
import re
import tkinter as tk
from tkinter import messagebox, ttk


# Núcleo aritmético del tabla
@dataclass(frozen=True, order=True)
class MValue:
    m: Fraction = Fraction(0)
    constant: Fraction = Fraction(0)

    def __add__(self, other):
        return MValue(self.m + other.m, self.constant + other.constant)

    def __sub__(self, other):
        return MValue(self.m - other.m, self.constant - other.constant)

    def scale(self, factor):
        return MValue(self.m * factor, self.constant * factor)

    def is_negative(self):
        return self < MValue()


def parse_number(value):
    return Fraction(value.strip())


def format_fraction(value):
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def format_mvalue(value):
    pieces = []
    if value.m:
        magnitude = format_fraction(abs(value.m))
        term = "M" if magnitude == "1" else f"{magnitude}M"
        pieces.append(("-" if value.m < 0 else "") + term)
    if value.constant:
        magnitude = format_fraction(abs(value.constant))
        sign = "-" if value.constant < 0 else "+"
        pieces.append(("" if not pieces and value.constant > 0 else sign + " ")
                      + magnitude)
    return " ".join(pieces) or "0"


def normalize_constraints(constraints):
    normalized = []
    for coefficients, relation, rhs in constraints:
        coefficients = list(coefficients)
        if rhs < 0:
            coefficients = [-value for value in coefficients]
            rhs = -rhs
            relation = {"<=": ">=", ">=": "<=", "=": "="}[relation]
        normalized.append((coefficients, relation, rhs))
    return normalized


def canonicalize_objective(rows, rhs, objective, objective_rhs, basis):
    for row_index, basic_col in enumerate(basis):
        factor = objective[basic_col]
        if factor != MValue():
            objective = [
                value - factor.scale(row_value)
                for value, row_value in zip(objective, rows[row_index])
            ]
            objective_rhs = objective_rhs - factor.scale(rhs[row_index])
    return objective, objective_rhs


def detect_identity_basis(rows, basis):
    selected = set(column for column in basis if column >= 0)
    for row_index, basic_col in enumerate(basis):
        if basic_col >= 0:
            continue
        identity_column = next((column for column in range(len(rows[0]))
                                if column not in selected
                                and all(row[column] == (1 if index == row_index else 0)
                                        for index, row in enumerate(rows))), None)
        if identity_column is None:
            return None
        basis[row_index] = identity_column
        selected.add(identity_column)
    return basis


def tabla_snapshot(title, names, rows, rhs, objective, objective_rhs, basis,
                     entering=None, leaving=None, pivot=None, ratios=None,
                     note=None):
    return {
        "title": title,
        "names": list(names),
        "rows": [list(row) for row in rows],
        "rhs": list(rhs),
        "objective": list(objective),
        "objective_rhs": objective_rhs,
        "basis": list(basis),
        "entering": entering,
        "leaving": leaving,
        "pivot": pivot,
        "ratios": ratios or [],
        "note": note,
    }


def run_simplex(rows, rhs, objective, objective_rhs, basis, names,
                artificial_cols, snapshots, phase, iteration_limit=500):
    snapshots.append(tabla_snapshot(
        f"{phase}: tabla inicial", names, rows, rhs, objective,
        objective_rhs, basis,
    ))

    iteration = 0
    while iteration < iteration_limit:
        candidates = [
            column for column, value in enumerate(objective)
            if column not in artificial_cols and value.is_negative()
        ]
        if not candidates:
            snapshots.append(tabla_snapshot(
                f"{phase}: solución óptima de la fase", names, rows, rhs,
                objective, objective_rhs, basis,
            ))
            return "optimal", objective_rhs

        entering_col = min(
            candidates,
            key=lambda column: (objective[column].m,
                                objective[column].constant, column),
        )
        ratios = []
        for row_index, row in enumerate(rows):
            coefficient = row[entering_col]
            if coefficient > 0:
                ratios.append((rhs[row_index] / coefficient, row_index))

        if not ratios:
            snapshots.append(tabla_snapshot(
                f"{phase}: problema no acotado", names, rows, rhs,
                objective, objective_rhs, basis,
                entering=names[entering_col],
                note="El problema tiene una Solución No Acotada (Ilimitada).",
            ))
            return "unbounded", objective_rhs

        minimum_ratio = min(value for value, _ in ratios)
        pivot_row = next(row_index for value, row_index in ratios
                         if value == minimum_ratio)
        leaving_col = basis[pivot_row]
        pivot_value = rows[pivot_row][entering_col]
        ratio_details = [
            (basis[row_index], value if rows[row_index][entering_col] > 0 else None)
            for row_index, value in enumerate(rhs)
        ]

        rows[pivot_row] = [value / pivot_value
                           for value in rows[pivot_row]]
        rhs[pivot_row] /= pivot_value
        for row_index, row in enumerate(rows):
            if row_index == pivot_row:
                continue
            factor = row[entering_col]
            if factor:
                rows[row_index] = [
                    value - factor * pivot_value_entry
                    for value, pivot_value_entry in zip(row, rows[pivot_row])
                ]
                rhs[row_index] -= factor * rhs[pivot_row]

        factor = objective[entering_col]
        if factor != MValue():
            objective = [
                value - factor.scale(row_value)
                for value, row_value in zip(objective, rows[pivot_row])
            ]
            objective_rhs = objective_rhs - factor.scale(rhs[pivot_row])
        basis[pivot_row] = entering_col
        iteration += 1

        snapshots.append(tabla_snapshot(
            f"{phase}: iteración {iteration}", names, rows, rhs, objective,
            objective_rhs, basis,
            entering=names[entering_col], leaving=names[leaving_col],
            pivot=pivot_value, ratios=ratio_details,
        ))

    snapshots.append(tabla_snapshot(
        f"{phase}: límite de iteraciones", names, rows, rhs,
        objective, objective_rhs, basis,
        note=f"Se alcanzó el límite de {iteration_limit} iteraciones.",
    ))
    return "iteration_limit", objective_rhs


def solve_linear_program(variable_count, costs, constraints, method,
                         objective_type):
    constraints = normalize_constraints(constraints)
    maximize = objective_type == "Maximizar"
    transformed_costs = list(costs) if maximize else [-value for value in costs]
    names = [f"x{index + 1}" for index in range(variable_count)]
    rows = []
    rhs = []
    basis = []
    artificial_cols = set()
    slack_count = 0
    artificial_count = 0
    generated_columns = 0

    for coefficients, relation, bound in constraints:
        row = list(coefficients)
        row.extend([Fraction(0)] * generated_columns)

        if relation == "<=":
            slack_count += 1
            names.append(f"s{slack_count}")
            for previous in rows:
                previous.append(Fraction(0))
            row.append(Fraction(1))
            generated_columns += 1
            basis.append(len(names) - 1)
        elif relation == ">=":
            slack_count += 1
            names.append(f"s{slack_count}")
            for previous in rows:
                previous.append(Fraction(0))
            row.append(Fraction(-1))
            generated_columns += 1
            if method == "Simplex":
                basis.append(-1)
            else:
                artificial_count += 1
                names.append(f"a{artificial_count}")
                for previous in rows:
                    previous.append(Fraction(0))
                row.append(Fraction(1))
                generated_columns += 1
                basis.append(len(names) - 1)
                artificial_cols.add(len(names) - 1)
        else:
            if method == "Simplex":
                basis.append(-1)
            else:
                artificial_count += 1
                names.append(f"a{artificial_count}")
                for previous in rows:
                    previous.append(Fraction(0))
                row.append(Fraction(1))
                generated_columns += 1
                basis.append(len(names) - 1)
                artificial_cols.add(len(names) - 1)

        rows.append(row)
        rhs.append(bound)

    for row in rows:
        row.extend([Fraction(0)] * (len(names) - len(row)))

    if method == "Simplex":
        basis = detect_identity_basis(rows, basis)
        if basis is None:
            return {
                "status": "no_initial_basis",
                "message": "Las restricciones no poseen variables de holgura "
                           "ni una matriz identidad detectable para iniciar "
                           "el Método Simplex. Usa Gran M o Dos Fases.",
                "snapshots": [],
            }

    snapshots = []
    objective = [MValue(constant=-cost) for cost in transformed_costs]
    objective.extend(MValue() for _ in range(len(names) - variable_count))
    objective_rhs = MValue()
    status = "optimal"

    if method == "Gran M":
        for column in artificial_cols:
            objective[column] = MValue(m=Fraction(1))
        objective, objective_rhs = canonicalize_objective(
            rows, rhs, objective, objective_rhs, basis,
        )
        status, objective_rhs = run_simplex(
            rows, rhs, objective, objective_rhs, basis, names,
            artificial_cols, snapshots, "Gran M",
        )
        if status == "optimal" and any(
                basis[row_index] in artificial_cols and rhs[row_index] > 0
                for row_index in range(len(basis))):
            status = "infeasible"
            snapshots.append(tabla_snapshot(
                "Gran M: problema infactible", names, rows, rhs, objective,
                objective_rhs, basis,
                note="El problema no tiene una Solución Básica Factible "
                     "(Infactible).",
            ))
    elif method == "Dos Fases" and artificial_cols:
        objective = [MValue() for _ in names]
        for column in artificial_cols:
            objective[column] = MValue(constant=Fraction(1))
        objective, objective_rhs = canonicalize_objective(
            rows, rhs, objective, objective_rhs, basis,
        )
        status, objective_rhs = run_simplex(
            rows, rhs, objective, objective_rhs, basis, names,
            artificial_cols, snapshots, "Fase I",
        )
        if status != "optimal":
            return {"status": status, "snapshots": snapshots}
        phase_one_artificial_value = sum(
            rhs[row_index] for row_index, basic_col in enumerate(basis)
            if basic_col in artificial_cols
        )
        if phase_one_artificial_value > 0:
            return {
                "status": "infeasible",
                "message": "El problema no tiene una Solución Básica "
                           "Factible (Infactible).",
                "snapshots": snapshots,
            }

        row_index = 0
        while row_index < len(basis):
            if basis[row_index] not in artificial_cols:
                row_index += 1
                continue
            entering_col = next((column for column in range(len(names))
                                 if column not in artificial_cols
                                 and column not in basis
                                 and rows[row_index][column] != 0), None)
            if entering_col is None:
                rows.pop(row_index)
                rhs.pop(row_index)
                basis.pop(row_index)
            else:
                pivot_value = rows[row_index][entering_col]
                rows[row_index] = [value / pivot_value
                                   for value in rows[row_index]]
                rhs[row_index] /= pivot_value
                for other_index, other_row in enumerate(rows):
                    if other_index == row_index:
                        continue
                    factor = other_row[entering_col]
                    if factor:
                        rows[other_index] = [
                            value - factor * pivot_entry
                            for value, pivot_entry in zip(other_row,
                                                          rows[row_index])
                        ]
                        rhs[other_index] -= factor * rhs[row_index]
                basis[row_index] = entering_col
                row_index += 1

        kept_columns = [column for column in range(len(names))
                         if column not in artificial_cols]
        column_map = {old: new for new, old in enumerate(kept_columns)}
        names = [names[column] for column in kept_columns]
        rows = [[row[column] for column in kept_columns] for row in rows]
        basis = [column_map[column] for column in basis]
        transformed_costs.extend(
            Fraction(0) for _ in range(len(kept_columns) - variable_count)
        )
        objective = [MValue(constant=-cost) for cost in transformed_costs]
        objective_rhs = MValue()
        artificial_cols = set()
        objective, objective_rhs = canonicalize_objective(
            rows, rhs, objective, objective_rhs, basis,
        )
        status, objective_rhs = run_simplex(
            rows, rhs, objective, objective_rhs, basis, names,
            artificial_cols, snapshots, "Fase II",
        )
    else:
        objective, objective_rhs = canonicalize_objective(
            rows, rhs, objective, objective_rhs, basis,
        )
        status, objective_rhs = run_simplex(
            rows, rhs, objective, objective_rhs, basis, names,
            artificial_cols, snapshots, method,
        )

    if status != "optimal":
        messages = {
            "unbounded": "El problema tiene una Solución No Acotada (Ilimitada).",
            "infeasible": "El problema no tiene una Solución Básica Factible "
                          "(Infactible).",
            "iteration_limit": "Se alcanzó el límite de iteraciones.",
        }
        return {"status": status, "message": messages.get(status),
                "snapshots": snapshots}

    values = [Fraction(0) for _ in range(variable_count)]
    for row_index, basic_col in enumerate(basis):
        if basic_col < variable_count:
            values[basic_col] = rhs[row_index]
    objective_value = sum(cost * value
                          for cost, value in zip(costs, values))
    return {
        "status": "optimal",
        "objective": objective_value,
        "values": values,
        "snapshots": snapshots,
    }


# Interfaz gráfica
class SimplexApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Actividad 3")
        self.root.geometry("1120x780")
        self.root.minsize(900, 620)
        self._configure_style()
        self._build_interface()

    def _configure_style(self):
        self.root.configure(background="#f2f5f4")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#f2f5f4")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("TLabel", background="#f2f5f4", foreground="#203432",
                        font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 20),
                        foreground="#153d39")
        style.configure("Sub.TLabel", foreground="#58706c")
        style.configure("Panel.TLabel", background="#ffffff")
        style.configure("PanelHead.TLabel", background="#ffffff",
                        foreground="#153d39", font=("Segoe UI Semibold", 11))
        style.configure("TButton", font=("Segoe UI Semibold", 10), padding=(12, 8))
        style.configure("Accent.TButton", background="#176b5e", foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", "#10564c")])
        style.configure("TCombobox", padding=5)

    def _build_interface(self):
        shell = ttk.Frame(self.root, padding=(24, 20))
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="Actividad 3",
                  style="Title.TLabel").pack(anchor="w")
        ttk.Label(shell, text="Método símplex · Gran M · Dos Fases",
                  style="Sub.TLabel").pack(anchor="w", pady=(3, 16))

        body = ttk.Panedwindow(shell, orient="horizontal")
        body.pack(fill="both", expand=True)
        input_panel = ttk.Frame(body, style="Panel.TFrame", padding=18)
        result_panel = ttk.Frame(body, style="Panel.TFrame", padding=18)
        body.add(input_panel, weight=1)
        body.add(result_panel, weight=2)

        ttk.Label(input_panel, text="Definición del problema",
                  style="PanelHead.TLabel").pack(anchor="w", pady=(0, 14))
        ttk.Label(input_panel, text="Método", style="Panel.TLabel").pack(anchor="w")
        self.method = ttk.Combobox(input_panel, state="readonly",
                                   values=("Simplex", "Gran M", "Dos Fases"))
        self.method.set("Simplex")
        self.method.pack(fill="x", pady=(4, 12))

        ttk.Label(input_panel, text="Formato de entrada",
                  style="Panel.TLabel").pack(anchor="w")
        self.form = ttk.Combobox(
            input_panel, state="readonly",
            values=("Canónica (<=)", "Estándar (=)", "General (<=, >=, =)"),
        )
        self.form.set("Canónica (<=)")
        self.form.pack(fill="x", pady=(4, 12))

        ttk.Label(input_panel, text="Objetivo", style="Panel.TLabel").pack(anchor="w")
        self.objective_type = ttk.Combobox(
            input_panel, state="readonly", values=("Maximizar", "Minimizar"),
        )
        self.objective_type.set("Maximizar")
        self.objective_type.pack(fill="x", pady=(4, 12))

        ttk.Label(input_panel, text="Número de variables",
                  style="Panel.TLabel").pack(anchor="w")
        self.variable_count = ttk.Spinbox(input_panel, from_=1, to=12,
                                          increment=1, width=8)
        self.variable_count.set("2")
        self.variable_count.pack(anchor="w", pady=(4, 12))

        ttk.Label(input_panel, text="Coeficientes de Z",
                  style="Panel.TLabel").pack(anchor="w")
        self.costs_entry = ttk.Entry(input_panel)
        self.costs_entry.insert(0, "3, 2")
        self.costs_entry.pack(fill="x", pady=(4, 12))

        ttk.Label(input_panel, text="Restricciones",
                  style="Panel.TLabel").pack(anchor="w")
        ttk.Label(input_panel, text="Una por línea: coeficientes <=, >= o = RHS",
                  style="Sub.TLabel", wraplength=300).pack(anchor="w", pady=(3, 5))
        self.constraints_entry = tk.Text(
            input_panel, height=9, wrap="none", font=("Cascadia Mono", 10),
            background="#f8faf9", foreground="#203432", relief="solid",
            borderwidth=1, padx=8, pady=8,
        )
        self.constraints_entry.insert(
            "1.0", "2, 1 <= 18\n2, 3 <= 42\n3, 1 <= 24",
        )
        self.constraints_entry.pack(fill="both", expand=True, pady=(0, 14))

        actions = ttk.Frame(input_panel, style="Panel.TFrame")
        actions.pack(fill="x")
        ttk.Button(actions, text="Resolver", style="Accent.TButton",
                   command=self.solve).pack(side="left")
        ttk.Button(actions, text="Limpiar resultados",
                   command=self.clear_results).pack(side="left", padx=(8, 0))

        ttk.Label(result_panel, text="Desarrollo y resultados",
                  style="PanelHead.TLabel").pack(anchor="w", pady=(0, 10))
        self.result = tk.Text(
            result_panel, wrap="none", state="disabled",
            font=("Cascadia Mono", 9), background="#fbfcfb",
            foreground="#203432", relief="solid", borderwidth=1,
            padx=12, pady=12,
        )
        vertical = ttk.Scrollbar(result_panel, orient="vertical",
                                 command=self.result.yview)
        horizontal = ttk.Scrollbar(result_panel, orient="horizontal",
                                   command=self.result.xview)
        self.result.configure(yscrollcommand=vertical.set,
                              xscrollcommand=horizontal.set)
        self.result.pack(side="left", fill="both", expand=True)
        vertical.pack(side="right", fill="y")
        horizontal.pack(side="bottom", fill="x")

    def _parse_problem(self):
        try:
            variable_count = int(self.variable_count.get())
            if not 1 <= variable_count <= 12:
                raise ValueError("El número de variables debe estar entre 1 y 12.")
            costs = [parse_number(part) for part in
                     re.split(r"[,;\s]+", self.costs_entry.get().strip()) if part]
            if len(costs) != variable_count:
                raise ValueError(
                    f"Se esperaban {variable_count} coeficientes para Z; "
                    f"se recibieron {len(costs)}."
                )

            constraints = []
            lines = [line.strip() for line in
                     self.constraints_entry.get("1.0", "end").splitlines()
                     if line.strip()]
            if not lines:
                raise ValueError("Ingresa al menos una restricción.")
            for line_number, line in enumerate(lines, start=1):
                normalized_line = line.replace("≤", "<=").replace("≥", ">=")
                match = re.fullmatch(r"(.+?)\s*(<=|>=|=)\s*(.+)",
                                     normalized_line)
                if not match:
                    raise ValueError(
                        f"La restricción {line_number} debe tener la forma "
                        "coeficientes <=, >= o = RHS."
                    )
                coefficient_text, relation, rhs_text = match.groups()
                coefficients = [parse_number(part) for part in
                                re.split(r"[,;\s]+", coefficient_text.strip())
                                if part]
                if len(coefficients) != variable_count:
                    raise ValueError(
                        f"La restricción {line_number} necesita "
                        f"{variable_count} coeficientes."
                    )
                constraints.append((coefficients, relation,
                                    parse_number(rhs_text)))
            relations = {relation for _, relation, _ in constraints}
            selected_form = self.form.get()
            if selected_form == "Canónica (<=)" and relations != {"<="}:
                raise ValueError(
                    "La forma canónica requiere restricciones <=. "
                    "Para otros signos, selecciona la forma general."
                )
            if selected_form == "Estándar (=)" and relations != {"="}:
                raise ValueError(
                    "La forma estándar requiere restricciones =. "
                    "Para desigualdades, selecciona la forma general."
                )
            return variable_count, costs, constraints
        except (ValueError, ZeroDivisionError) as error:
            raise ValueError(f"Datos de entrada inválidos: {error}") from error

    def solve(self):
        try:
            variable_count, costs, constraints = self._parse_problem()
            result = solve_linear_program(
                variable_count, costs, constraints, self.method.get(),
                self.objective_type.get(),
            )
            self._show_result(result, variable_count)
            if result["status"] != "optimal":
                messagebox.showwarning(
                    "No se obtuvo un óptimo", result.get(
                        "message", "El problema no tiene solución óptima."
                    ),
                )
        except ValueError as error:
            messagebox.showerror("Revisa los datos", str(error))

    def _show_result(self, result, variable_count):
        self.result.configure(state="normal")
        self.result.delete("1.0", "end")
        if result.get("snapshots"):
            for snapshot in result["snapshots"]:
                self._write_snapshot(snapshot)
        if result["status"] == "optimal":
            self.result.insert("end", "\nRESULTADO ÓPTIMO\n")
            self.result.insert(
                "end", f"Z = {format_fraction(result['objective'])}\n",
            )
            for index, value in enumerate(result["values"][:variable_count]):
                self.result.insert("end", f"x{index + 1} = {format_fraction(value)}\n")
        else:
            message = result.get("message", "No se encontró una solución óptima.")
            self.result.insert("end", f"\nESTADO: {result['status'].upper()}\n{message}\n")
        self.result.configure(state="disabled")

    def _write_snapshot(self, snapshot):
        self.result.insert("end", f"\n{snapshot['title']}\n")
        names = snapshot["names"]
        basis_names = [names[column] for column in snapshot["basis"]]
        headers = ["Base"] + names + ["Solución"]
        data = []
        for row_index, row in enumerate(snapshot["rows"]):
            data.append([basis_names[row_index]]
                        + [format_fraction(value) for value in row]
                        + [format_fraction(snapshot["rhs"][row_index])])
        data.append(["Z"] + [format_mvalue(value)
                              for value in snapshot["objective"]]
                    + [format_mvalue(snapshot["objective_rhs"])])
        widths = [max(len(headers[index]), *(len(line[index]) for line in data))
                  for index in range(len(headers))]
        self.result.insert("end", "  ".join(
            value.ljust(widths[index]) for index, value in enumerate(headers)
        ) + "\n")
        for line in data:
            self.result.insert("end", "  ".join(
                value.ljust(widths[index]) for index, value in enumerate(line)
            ) + "\n")
        if snapshot["entering"]:
            pivot_display = (format_fraction(snapshot["pivot"])
                             if snapshot["pivot"] is not None else "N/A")
            self.result.insert(
                "end", f"Entra: {snapshot['entering']} | "
                f"Sale: {snapshot['leaving'] or 'ninguna'} | "
                f"Pivote: {pivot_display}\n",
            )
            if snapshot["ratios"]:
                ratios = []
                for basic_col, ratio in snapshot["ratios"]:
                    ratios.append(f"{names[basic_col]}: " + (
                        format_fraction(ratio) if ratio is not None
                        else "no se toma"
                    ))
                self.result.insert("end", "Razones: " + " | ".join(ratios) + "\n")
        if snapshot["note"]:
            self.result.insert("end", snapshot["note"] + "\n")

    def clear_results(self):
        self.result.configure(state="normal")
        self.result.delete("1.0", "end")
        self.result.configure(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    SimplexApp(root)
    root.mainloop()